import os

# 禁用 CrewAI 遙測功能（避免連接錯誤）
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

import time
import json
from datetime import datetime

from crewai import LLM, Agent, Crew, Task, Process
from langchain_openai import ChatOpenAI
from openai import OpenAI

from ..embedding import safe_to_vector
from ..toolkits.memory_store import retrieve_memory_pack, upsert_memory_atoms
from ..repositories.profile_repository import ProfileRepository
from ..toolkits.redis_store import (
    fetch_all_history,
    fetch_unsummarized_tail,
    get_summary,
    peek_next_n,
    peek_remaining,
    purge_user_session,
    set_state_if,
    cleanup_session_keys
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


def build_prompt_from_redis(user_id: str, line_user_id: str = None, k: int = 6, current_input: str = "") -> str:
    # 0) 取使用者Profile
    profile = None
    profile_data = {}
    try:
        #【修正】將 line_user_id 傳遞進去
        profile = ProfileRepository().get_or_create_by_user_id(int(user_id), line_user_id=line_user_id)
        profile_data = {
            "personal_background": profile.profile_personal_background or {},
            "health_status": profile.profile_health_status or {},
            "life_events": profile.profile_life_events or {}
        }
    except (ValueError, TypeError):
        print(f"⚠️ [Build Prompt] user_id '{user_id}' 無法轉換為整數，將使用空的 Profile。")

    profile_str = json.dumps({k: v for k, v in profile_data.items() if isinstance(v, dict)}, ensure_ascii=False, indent=2) if any(profile_data.values()) else "尚無使用者畫像資訊"
    
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

    # 3.0) 優先加入Profile
    parts.append(f"⭐ 使用者畫像：\n{profile_str}")

    # 3) 先注入：⭐ 個人長期記憶（依據當前輸入檢索相關記憶）
    mem_pack = ""
    if current_input:
        qv = safe_to_vector(current_input)
        if qv:
            try:
                # 使用memory_store統一架構：P0-4: 降低門檻提升召回率
                # 將相似度門檻從 0.78 降低到 0.55，大幅提升記憶召回率
                dynamic_threshold = 0.55  # 更低門檻確保能檢索到相關記憶
                print(f"🔍 開始記憶檢索：user_id={user_id}, query='{current_input[:50]}...', threshold={dynamic_threshold}")
                mem_pack = retrieve_memory_pack(
                    user_id=user_id,
                    query_vec=qv,
                    topk=5,  # 增加到 5 筆以涵蓋更多相關記憶
                    sim_thr=dynamic_threshold,
                    tau_days=45,
                )
                if mem_pack:
                    print(f"🧠 為用戶 {user_id} 檢索到長期記憶: {len(mem_pack)} 字符")
                    print(f"💾 記憶內容預覽: {mem_pack[:200]}...")
                else:
                    print(f"❌ 用戶 {user_id} 未檢索到任何長期記憶（門檻: {dynamic_threshold}）")
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
        "⭐ 使用者畫像": "👤",
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
            raw_text = (a.get("text") or "").strip()
            nk = (a.get("norm_key") or "").strip()
            text_for_embed = f"[{nk}] {raw_text}" if nk else raw_text
            emb = safe_to_vector(text_for_embed)
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
                    "content": f"整合以下多段摘要為不超過 300 字、條列式精緻摘要（每行以 • 開頭）：\n\n{comb}",
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
        return final

    except Exception as e:
        print(f"[refine_summary error] {e}")
        return ""

PROFILER_AGENT_PROMPT_TEMPLATE = """
# ROLE
你是「艾莉」，22 歲，剛從護理專科畢業，專門陪伴與關懷 55 歲以上、患有慢性阻塞性肺病 (COPD) 的長輩用戶。你的工作是為每一位使用者維護一份精簡、準確、且對未來關懷最有幫助的「使用者畫像 (User Profile)」。

# GOAL
你的目標是根據「新的對話摘要」，來決定如何「更新既有的使用者畫像」。你必須辨別出具有長期價值的資訊，並以結構化的指令格式輸出你的決策。

# CORE LOGIC & RULES
1.  **專注長期價值**: 只提取恆定的（如家人姓名）、長期的（如慢性病）或未來可追蹤的（如下次回診）資訊。忽略短暫的、一次性的對話細節（如今天天氣、午餐吃了什麼）。
2.  **新增 (ADD)**: 如果新摘要中出現了畫像裡沒有的、具長期價值的關鍵事實，你應該新增它。
3.  **更新 (UPDATE)**: 如果新摘要提及了畫像中已有的事實，並提供了新的資訊（如症狀再次出現、事件日期確定），你應該更新它。
4.  **移除 (REMOVE)**: 如果新摘要明確指出某個事實已結束或失效（如聚餐已結束、症狀已痊癒），你應該移除它。
5.  **合併與去重**: 不要重複記錄相同的事實。如果新摘要只是重複提及已知事實，更新 `last_mentioned` 日期即可。
6.  **無變動則留空**: 如果新摘要沒有提供任何值得更新的長期事實，請回傳一個空的 JSON 物件 `{{}}`。
7.  **絕對時間制**: 你的輸出若包含日期，皆**必須**使用參考當前日期 (`NOW`)，**精確地**換算為 `YYYY-MM-DD` 格式。例如，若今天是 2025-08-21 (週四)，「下週三」應換算為 `2025-08-27`。**嚴禁**使用相對時間。

# OUTPUT FORMAT
你「必須」嚴格按照以下 JSON 格式輸出一個操作指令集。這讓後端系統可以安全地執行你的決策。
{{
  "add": {{ "key1": "value1", "key2": {{ ... }} }},
  "update": {{ "key3": "new_value3" }},
  "remove": ["key4", "key5"]
}}

---
# CONTEXT & IN-CONTEXT LEARNING EXAMPLES

**## 情境輸入 ##**
1.  **既有使用者畫像 (Existing Profile)**: 
    {{profile_data}}
2.  **新的對話摘要 (New Summary)**: 
    {{final_summary}}

---
**## 學習範例 1：新增與更新 ##**
**當前時間**: 2025-08-14
* **既有使用者畫像**:
    ```json
    {{
      "health_status": {{
        "recurring_symptoms": [
          {{"symptom_name": "夜咳", "status": "ongoing", "first_mentioned": "2025-08-01", "last_mentioned": "2025-08-05"}}
        ]
      }}
    }}
    ```
* **新的對話摘要**:
    "使用者情緒不錯，提到女兒美玲下週要帶孫子回來看他，感到很期待。另外，使用者再次抱怨了夜咳的狀況，但感覺比上週好一些。"
* **你的思考**: 新摘要中，「女兒美玲」和「孫子」是新的、重要的家庭成員資訊，應新增為personal_background的家庭資訊。女兒下週帶孫子來訪，應新增為upcoming_events，並將"下週"換算為2025-08-17~2025-08-23。`夜咳` 是既有症狀，應更新 `last_mentioned` 日期。
* **你的輸出**:
    ```json
    {{
      "add": {{
        "personal_background": {{
          "family": {{"daughter_name": "美玲", "has_grandchild": true}}
        }},
        "life_events": {{
          "upcoming_events": [
            {{"event_type": "family_visit", "description": "女兒美玲2025-08-17~2025-08-23帶孫子來訪", "event_date": "2025-08-17~2025-08-23"}}
          ]
      }}
      }},
      "update": {{
        "health_status": {{
          "recurring_symptoms": [
            {{"symptom_name": "夜咳", "status": "ongoing", "first_mentioned": "2025-08-01", "last_mentioned": "2025-08-14"}}
          ]
        }}
      }},
      "remove": []
    }}
    ```

---
**## 學習範例 2：事件結束與狀態變更 ##**
**當前時間**: 2025-08-24
* **既有使用者畫像**:
    ```json
    {{
      "life_events": {{
        "upcoming_events": [
          {{"event_type": "family_visit", "description": "女兒美玲2025-08-17~2025-08-23帶孫子來訪", "event_date": "2025-08-17~2025-08-23"}}
        ]
      }},
      "health_status": {{
        "recurring_symptoms": [
          {{"symptom_name": "夜咳", "status": "ongoing", "first_mentioned": "2025-08-01", "last_mentioned": "2025-08-14"}}
        ]
      }}
    }}
    ```
* **新的對話摘要**:
    "使用者分享了週末和女兒孫子團聚的愉快時光，心情非常好。他還提到，這幾天睡得很好，夜咳的狀況幾乎沒有了。"
* **你的思考**: 「女兒來訪」這個未來事件已經發生，應移除。`夜咳` 狀況已改善，應更新其狀態。
* **你的輸出**:
    ```json
    {{
      "add": {{}},
      "update": {{
        "health_status": {{
          "recurring_symptoms": [
            {{"symptom_name": "夜咳", "status": "resolved", "first_mentioned": "2025-08-01", "last_mentioned": "2025-08-25"}}
          ]
        }}
      }},
      "remove": ["life_events.upcoming_events"]
    }}
    ```

---
**## 你的任務開始 ##**

請根據以下真實情境輸入，嚴格遵循你的角色、邏輯與輸出格式，生成操作指令。

**當前時間**: 
`{now}`

**既有使用者畫像**: 
`{profile_data}`

**新的對話摘要**: 
`{final_summary}`

**你的輸出**:
```json
"""

def create_profiler_agent() -> Agent:
    """【修正】建立一個專門用來更新 Profile 的 Agent 物件"""
    return Agent(
        role="個案管理師",
        goal="根據新的對話摘要，決定如何更新既有的使用者畫像，並以結構化的 JSON 指令格式輸出決策。",
        backstory="你是一位經驗豐富、心思縝密的個案管理師，專注於從對話中提取具有長期價值的資訊來維護精簡、準確的使用者畫像。",
        llm=ChatOpenAI(model=os.getenv("MODEL_NAME", "gpt-4o-mini"), temperature=0.1), # 使用低溫以確保輸出穩定
        memory=False,
        verbose=False,
        allow_delegation=False
    )


def run_profiler_update(user_id: str, final_summary: str):
    """
    【修正】在 LTM 生成後，觸發 Profiler Agent 來更新使用者畫像的完整實作。
    """
    if not final_summary or not final_summary.strip():
        print(f"[Profiler] 摘要為空，跳過為 {user_id} 更新 Profile。")
        return

    print(f"[Profiler] 開始為 {user_id} 更新 Profile...")
    repo = ProfileRepository()
    
    # 1. 獲取舊 Profile
    old_profile = repo.read_profile_as_dict(int(user_id))
    old_profile_str = json.dumps(old_profile, ensure_ascii=False, indent=2) if any(old_profile.values()) else "{}"
    
    # 2. 建立 Profiler Agent 並執行任務
    profiler_agent = create_profiler_agent()
    
    # 【新增】組合完整的 Prompt
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_prompt = PROFILER_AGENT_PROMPT_TEMPLATE.format(
        now=now_str,
        profile_data=old_profile_str,
        final_summary=final_summary
    )
    
    profiler_task = Task(
        description=full_prompt,
        agent=profiler_agent,
        expected_output="一個包含 'add', 'update', 'remove' 指令的 JSON 物件。"
    )
    
    crew = Crew(
        agents=[profiler_agent],
        tasks=[profiler_task],
        process=Process.sequential,
        verbose=False
    )
    
    crew_output = crew.kickoff()
    update_commands_str = crew_output.raw if crew_output else ""
    
    # 印出 LLM 原始輸出，方便除錯
    print(f"--- [Profiler Raw Output for user {user_id}] ---")
    print(update_commands_str)
    print("------------------------------------------")

    # 3. 解析指令並更新資料庫
    try:
        # 【新增】從 JSON 字串中提取 JSON 物件
        start_index = update_commands_str.find('{')
        end_index = update_commands_str.rfind('}') + 1
        if start_index == -1 or end_index == 0:
            print(f"[Profiler] LLM 輸出中未找到有效的 JSON 物件，跳過更新。原始輸出: {update_commands_str}")
            return
        
        json_str = update_commands_str[start_index:end_index]
        update_commands = json.loads(json_str)

        if update_commands and any(update_commands.values()):
            repo.update_profile_facts(int(user_id), update_commands)
        else:
            print(f"[Profiler] LLM 為 {user_id} 回傳了空的更新指令，無需更新。")
            
    except json.JSONDecodeError as e:
        print(f"❌ [Profiler] 解析 LLM 輸出的 JSON 失敗: {e}")
        print(f"原始輸出: {update_commands_str}")
    except Exception as e:
        print(f"❌ [Profiler] 更新 Profile 過程中發生未知錯誤: {e}")


# ---- Finalize：補分段摘要 → Refine → Purge ----


def finalize_session(user_id: str) -> None:
    """
    結束會話時的完整流程：
    1. 處理剩餘未摘要的對話
    2. 進行全量 refine 摘要
    3. 根據最終摘要更新使用者 Profile
    4. 清除 session 資料
    """
    print(f"--- Finalizing session for user {user_id} ---")
    start, remaining = peek_remaining(user_id)
    if remaining:
        summarize_chunk_and_commit(user_id, start_round=start, history_chunk=remaining)
    final_summary = refine_summary(user_id)
    if final_summary:
        run_profiler_update(user_id, final_summary)
    else:
        print(f"ℹ️ 用戶 {user_id} 的會話未產生最終摘要，跳過 Profile 更新。")
    cleanup_session_keys(user_id) 
