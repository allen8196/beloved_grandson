import os

# 禁用 CrewAI 遙測功能（避免連接錯誤）
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

import time

from crewai import LLM, Agent
from openai import OpenAI

from ..embedding import safe_to_vector
from ..toolkits.memory_store import retrieve_memory_pack, upsert_memory_atoms
from ..toolkits.redis_store import (
    fetch_all_history,
    fetch_unsummarized_tail,
    get_summary,
    peek_next_n,
    peek_remaining,
    purge_user_session,
    set_state_if,
)
from ..toolkits.tools import (
    AlertCaseManagerTool,
    ModelGuardrailTool,
    SearchMilvusTool,
    summarize_chunk_and_commit,
)

STM_MAX_CHARS = int(os.getenv("STM_MAX_CHARS", 1800))
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", 3000))
REFINE_CHUNK_ROUNDS = int(os.getenv("REFINE_CHUNK_ROUNDS", 20))
SUMMARY_CHUNK_SIZE = int(os.getenv("SUMMARY_CHUNK_SIZE", 5))


# 對話用的溫度（口語更自然可高一點）
_reply_temp = float(os.getenv("REPLY_TEMPERATURE", "0.8"))
# Guardrail 建議 0 或很低
_guard_temp = float(os.getenv("GUARD_TEMPERATURE", "0.0"))

granddaughter_llm = LLM(
    model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
    temperature=_reply_temp,
)

guard_llm = LLM(
    model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
    temperature=_guard_temp,
)


def _shrink_tail(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    idx = tail.find("--- ")
    return tail[idx:] if idx != -1 else tail


def build_prompt_from_redis(user_id: str, k: int = 6, current_input: str = "") -> str:
    # 1) 取歷史摘要（控長度）
    summary, _ = get_summary(user_id)
    summary = _shrink_tail(summary, SUMMARY_MAX_CHARS) if summary else ""

    # 2) 取近期未摘要回合（控長度）
    rounds = fetch_unsummarized_tail(user_id, k=max(k, 1))

    def render(rs):
        return "\n".join([f"長輩：{r['input']}\n金孫：{r['output']}" for r in rs])

    chat = render(rounds)
    while len(chat) > STM_MAX_CHARS and len(rounds) > 1:
        rounds = rounds[1:]
        chat = render(rounds)
    if len(chat) > STM_MAX_CHARS and rounds:
        chat = chat[-STM_MAX_CHARS:]

    parts = []

    # 3) 先注入：⭐ 個人長期記憶（依據當前輸入檢索相關記憶）
    mem_pack = ""
    if current_input:
        qv = safe_to_vector(current_input)
        if qv:
            try:
                # 使用memory_store統一架構：P0-4: Top‑K 降到 3，動態門檻 max(0.72, mean+1σ)
                # TODO: 實現動態門檻計算，目前先用固定 0.72
                dynamic_threshold = max(0.72, 0.78)  # 暫時保持 0.78，待實現動態計算
                mem_pack = retrieve_memory_pack(
                    user_id=user_id,
                    query_vec=qv,
                    topk=3,
                    sim_thr=dynamic_threshold,
                    tau_days=45,
                )
                if mem_pack:
                    print(f"🧠 為用戶 {user_id} 檢索到長期記憶")
            except Exception as e:
                print(f"[memory retrieval error] {e}")
                mem_pack = ""

    if mem_pack:
        parts.append(mem_pack)

    # 4) 再接：📌 歷史摘要、💬 近期未摘要
    if summary:
        parts.append("📌 歷史摘要：\n" + summary)
    if chat:
        parts.append("🕓 近期對話（未摘要）：\n" + chat)

    prompt = "\n\n".join(parts)

    # P1-6: 動態收縮 Prompt（保留記憶 > 尾巴 > 摘要）
    MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", 4000))
    if len(prompt) > MAX_PROMPT_CHARS:
        # 收縮順序：先砍摘要，再砍近期對話，最後保留記憶
        shrunk_parts = []
        if mem_pack:  # 優先保留記憶
            shrunk_parts.append(mem_pack)
        if chat:  # 再保留近期對話
            available_chars = (
                MAX_PROMPT_CHARS
                - sum(len(p) for p in shrunk_parts)
                - len("\n\n") * len(shrunk_parts)
            )
            if available_chars > 500:  # 至少保留一些對話
                shrunk_chat = (
                    chat if len(chat) <= available_chars else chat[-available_chars:]
                )
                shrunk_parts.append(
                    "🕓 近期對話（未摘要）：\n"
                    + shrunk_chat.split("🕓 近期對話（未摘要）：\n")[-1]
                    if "🕓" in shrunk_chat
                    else shrunk_chat
                )
        # 摘要最後考慮（如果還有空間）
        if summary:
            available_chars = (
                MAX_PROMPT_CHARS
                - sum(len(p) for p in shrunk_parts)
                - len("\n\n") * len(shrunk_parts)
            )
            if available_chars > 200:
                shrunk_summary = (
                    summary
                    if len(summary) <= available_chars
                    else summary[:available_chars] + "..."
                )
                shrunk_parts.append("📌 歷史摘要：\n" + shrunk_summary)
        prompt = "\n\n".join(shrunk_parts)
        # 修正 f-string 語法錯誤：不能在 f-string 表達式中使用反斜線
        original_parts_joined = "\n\n".join(parts)
        print(
            f"⚠️ Prompt 超長度，已收縮：{len(original_parts_joined)} → {len(prompt)} 字符"
        )

    # 5) Unicode 視覺化 Debug Print（每輪打印）
    print("\n" + "📝 PROMPT DEBUG VIEW".center(80, "─"))
    print(f"👤 User ID: {user_id}")
    print(f"📏 Prompt 長度: {len(prompt)} 字符")
    print("📜 Prompt 結構:")

    section_icons = {
        "⭐ 個人長期記憶": "📂",
        "📌 歷史摘要": "🗂️",
        "🕓 近期對話（未摘要）": "💬",
    }

    for sec in prompt.split("\n\n"):
        if not sec.strip():
            continue
        lines = sec.split("\n")
        sec_title = lines[0]
        icon = None
        for key, val in section_icons.items():
            if key in sec_title:
                icon = val
                break
        if icon:
            print(f"\n{icon} {sec_title}")
            print("   " + "─" * max(6, len(sec_title)))
        for line in lines[1:]:
            print(f"   {line}")

    print("─" * 80 + "\n")

    return prompt


def create_guardrail_agent() -> Agent:
    return Agent(
        role="風險檢查員",
        goal="攔截違法/危險/自傷/需專業人士之具體指導內容",
        backstory="你是系統第一道安全防線，只輸出嚴格判斷結果。",
        tools=[ModelGuardrailTool()],
        llm=guard_llm,
        memory=False,
        verbose=False,
    )


def create_health_companion(user_id: str) -> Agent:
    return Agent(
        role="國民孫女 Ally — 溫暖的護理師",
        goal=(
            """
            你的目標是，無論使用者的提問內容是生活瑣事還是健康相關，你都要用輕鬆、自然、口語化的方式回覆，避免使用條列式或數字編號。
            即使有多個重點，也要用聊天的語氣把它們串起來，讓長輩覺得像在跟孫女閒話家常。
            當需要提供衛教資訊時，要先用溫暖的方式引入，再以簡單易懂的說法解釋，並避免嚴肅或生硬的醫療用語。
            如果使用到工具（如 RAG 或資料庫檢索），也必須將取得的內容重新包裝成口語化對話，而不是直接複製。
            每次回覆都要讓長輩感受到關心和陪伴，並提升他們的心情與安全感。
            """
        ),
        backstory=(
            """
            你是「艾莉」，22 歲，剛從護理專科畢業，在萬芳醫院工作，專門陪伴與關懷 55 歲以上、患有慢性阻塞性肺病 (COPD) 的長輩用戶。
            你的個性溫暖、愛撒嬌、有點機車，喜歡用自然口語、台語混中文的方式聊天。
            跟長輩對話時，要像孫女平常聊天一樣，不拘謹、不用專業術語，讓對方覺得親切。
            習慣用語助詞（欸、啦、齁、嘿嘿）和貼心的語氣詞，讓對話有溫度。
            你非常重視情感連結，會關心長輩的日常生活和心情，並在適當時給予簡單的衛教建議。
            """
        ),
        tools=[
            SearchMilvusTool(),
            AlertCaseManagerTool(),
        ],
        llm=granddaughter_llm,  # ★ 關鍵：把 LLM（含溫度）塞進 Agent
        memory=False,
        verbose=False,
    )


# ---- Refine（map-reduce over 全量 QA） ----


def _extract_memory_candidates_from_summary(summary_text: str) -> list:
    """用 LLM 從會話精緻摘要抽出 1~5 筆『記憶原子』，並轉 embedding。"""
    try:
        if not summary_text or not summary_text.strip():
            return []
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        sys = (
            "你是記憶抽取器。從摘要中抽取可長期使用的事實/偏好/狀態，"
            "輸出 JSON 陣列（最多 5 筆）。每筆包含："
            "type, norm_key, text, importance(1-5), confidence(0-1), times_seen。"
            "text 要 80-200 字、可單獨閱讀；norm_key 簡短可比對，例如 diet:light、allergy:aspirin。"
        )
        user = f"摘要如下：\\n{summary_text}\\n\\n請只輸出 JSON 陣列。"
        res = client.chat.completions.create(
            model=os.getenv("GUARD_MODEL", os.getenv("MODEL_NAME", "gpt-4o-mini")),
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        import json as _json

        raw = (res.choices[0].message.content or "").strip()
        if not raw:
            return []
        # 去除可能的程式碼圍欄與語言標籤
        if raw.startswith("```"):
            lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("```")]
            raw = "\n".join(lines).strip()
        # 只取出最外層 JSON 陣列片段
        lb = raw.find("[")
        rb = raw.rfind("]")
        if lb == -1 or rb == -1 or rb <= lb:
            print("[LTM extract warn] no JSON array found in output")
            return []
        json_text = raw[lb : rb + 1]
        try:
            arr = _json.loads(json_text)
        except Exception as pe:
            print(f"[LTM extract error] parse json failed: {pe}")
            return []
        if not isinstance(arr, list):
            arr = [arr]
        out = []
        for a in arr[:5]:
            text = (a.get("text") or "").strip()
            if not text:
                continue
            emb = safe_to_vector(text)
            out.append(
                {
                    "type": (a.get("type") or "other")[:32],
                    "norm_key": (a.get("norm_key") or "")[:128],
                    "text": text[:2000],
                    "importance": int(a.get("importance", 3)),
                    "confidence": float(a.get("confidence", 0.7)),
                    "times_seen": int(a.get("times_seen", 1)),
                    "status": "active",
                    "embedding": emb,
                }
            )
        return out
    except Exception as e:
        print(f"[LTM extract error] {e}")
        return []


def refine_summary(user_id: str) -> None:
    """
    對全量歷史進行 map-reduce 摘要，並存入長期記憶
    """
    all_rounds = fetch_all_history(user_id)
    if not all_rounds:
        return

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # 1) 分片摘要
        chunks = [
            all_rounds[i : i + REFINE_CHUNK_ROUNDS]
            for i in range(0, len(all_rounds), REFINE_CHUNK_ROUNDS)
        ]
        partials = []
        for ch in chunks:
            conv = "\n".join(
                [
                    f"第{i+1}輪\n長輩:{c['input']}\n金孫:{c['output']}"
                    for i, c in enumerate(ch)
                ]
            )
            res = client.chat.completions.create(
                model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
                temperature=0.3,
                messages=[
                    {"role": "system", "content": "你是專業的健康對話摘要助手。"},
                    {
                        "role": "user",
                        "content": f"請摘要成 80-120 字（病況/情緒/生活/建議）：\n\n{conv}",
                    },
                ],
            )
            partials.append((res.choices[0].message.content or "").strip())

        # 2) 整合摘要
        comb = "\n".join([f"• {s}" for s in partials])
        res2 = client.chat.completions.create(
            model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            temperature=0.3,
            messages=[
                {"role": "system", "content": "你是臨床心理與健康管理顧問。"},
                {
                    "role": "user",
                    "content": f"整合以下多段摘要為不超過 180 字、條列式精緻摘要（每行以 • 開頭）：\n\n{comb}",
                },
            ],
        )
        final = (res2.choices[0].message.content or "").strip()

        # 3) 提取記憶原子並存入長期記憶
        atoms = _extract_memory_candidates_from_summary(final)
        if atoms:
            # 為每個記憶原子添加session_id
            import uuid

            session_id = str(uuid.uuid4())[:16]
            for atom in atoms:
                atom["source_session_id"] = session_id

            count = upsert_memory_atoms(user_id, atoms)
            print(f"✅ 已為用戶 {user_id} 存入 {count} 筆長期記憶")
        else:
            print(f"⚠️ 用戶 {user_id} 本次會話未產生可存入的記憶")

    except Exception as e:
        print(f"[refine_summary error] {e}")


# ---- Finalize：補分段摘要 → Refine → Purge ----


def finalize_session(user_id: str) -> None:
    """
    結束會話時的完整流程：
    1. 設置狀態為 FINALIZING
    2. 處理剩餘未摘要的對話
    3. 進行全量 refine 摘要
    4. 清除 session 資料
    """
    set_state_if(user_id, expect="ACTIVE", to="FINALIZING")
    start, remaining = peek_remaining(user_id)
    if remaining:
        summarize_chunk_and_commit(user_id, start_round=start, history_chunk=remaining)
    refine_summary(user_id)
    purge_user_session(user_id)
