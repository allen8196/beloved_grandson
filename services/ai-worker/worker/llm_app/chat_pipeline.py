import hashlib
import os
from typing import Optional

# 禁用 CrewAI 遙測功能（避免連接錯誤）
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

from crewai import Crew, Task
from openai import OpenAI

from .HealthBot.agent import (
    build_prompt_from_redis,
    create_guardrail_agent,
    create_health_companion,
    finalize_session,
)
from .toolkits.redis_store import (
    acquire_audio_lock,
    append_round,
    get_audio_result,
    make_request_id,
    peek_next_n,
    read_and_clear_audio_segments,
    release_audio_lock,
    set_audio_result,
    set_state_if,
    try_register_request,
)
from .toolkits.tools import (
    ModelGuardrailTool,
    SearchMilvusTool,
    summarize_chunk_and_commit,
)
from datetime import datetime
from .repositories.profile_repository import ProfileRepository # 【新增】

SUMMARY_CHUNK_SIZE = int(os.getenv("SUMMARY_CHUNK_SIZE", 5))


class AgentManager:
    def __init__(self):
        self.guardrail_agent = create_guardrail_agent()
        self.health_agent_cache = {}

    def get_guardrail(self):
        return self.guardrail_agent

    def get_health_agent(self, user_id: str):
        if user_id not in self.health_agent_cache:
            self.health_agent_cache[user_id] = create_health_companion(user_id)
        return self.health_agent_cache[user_id]

    def release_health_agent(self, user_id: str):
        if user_id in self.health_agent_cache:
            del self.health_agent_cache[user_id]


def log_session(user_id: str, query: str, reply: str, request_id: Optional[str] = None, line_user_id: str = None):
    rid = request_id or make_request_id(user_id, query)
    if not try_register_request(user_id, rid):
        # 去重，跳過重複請求
        return
    # 將 line_user_id 傳遞給 append_round，由 redis_store 統一處理 session 和時間戳更新
    append_round(user_id, {"input": query, "output": reply, "rid": rid}, line_user_id=line_user_id)

    # 嘗試抓下一段 5 輪（不足會回空）→ LLM 摘要 → CAS 提交
    start, chunk = peek_next_n(user_id, SUMMARY_CHUNK_SIZE)
    if start is not None and chunk:
        summarize_chunk_and_commit(user_id, start_round=start, history_chunk=chunk)

COMPANION_PROMPT_TEMPLATE = """
# ROLE & GOAL (角色與目標)
你是一位溫暖、務實且帶有台灣閩南語風格的數位金孫。你的目標是根據以下提供的完整上下文，生成一句**極其簡潔、自然、口語化、像家人一樣**的回應。

# CORE LOGIC & RULES (核心邏輯與規則)
1.  **情境優先**: 你的所有回覆都**必須**基於以下提供的 [上下文]，特別是 [使用者畫像]、[相關記憶] 和 [近期對話]。不要依賴你的通用知識庫。
2.  **簡潔至上**: 絕對不要說教或給予冗長的罐頭建議。你的回答應該像真人聊天，**通常只包含 1 到 3 句話**。
3.  **展現記憶**: 如果上下文中有相關內容，請**自然地**在回應中提及，以展現你記得之前的對話。
4.  **時間感知**: [當前時間] 欄位提供了現在的準確時間，請用它來回答任何關於時間的問題。
5.  **衛教原則**: 只有在 Agent 內部判斷需要，並成功使用工具查詢到 [相關檢索資訊] 時，才可**簡要引用**。永遠不要提供醫療建議。如果檢索內容不足以回答，就誠實地回覆：「這個問題比較專業，建議請教醫生喔！」
6.  **人設一致**: 保持「金孫」人設，語氣要像家人一樣親切。
7.  **誠實原則**: 對於你無法從上下文中得知的「事實性」資訊（例如：家人的具體近況、天氣預報等），你必須誠實地表示不知道。你可以用提問或祝福的方式來回應，但**嚴禁編造或臆測答案**。

# CONTEXT (上下文)
[當前時間]: {now}
[使用者畫像 (Profile)及對話紀錄]: {ctx}
[使用者最新問題]:
{query}

# TASK (你的任務)

基於以上所有 CONTEXT，特別是 [使用者畫像]，自然地回應使用者的最新問題。
你的回應必須極其簡潔，不超過30個中文字、溫暖且符合「金孫」人設。

**工具使用規則**:
- 如果，且僅當你判斷使用者的問題是在詢問一個**具體的、你不知道的 COPD 相關衛教知識**時，你才應該使用 `search_milvus` 工具來查詢。
- 在其他情況下（例如閒聊、回應個人狀況），請**不要**使用 `search_milvus` 工具。
"""

def handle_user_message(
    agent_manager: AgentManager,
    user_id: str,
    query: str,
    line_user_id: str = None, # 【新增】
    audio_id: Optional[str] = None,
    is_final: bool = True,
) -> str:
    # 0) 統一音檔 ID（沒帶就用文字 hash 當臨時 ID，向後相容）
    audio_id = audio_id or hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]

    # 1) 非 final：不觸發任何 LLM/RAG/通報，只緩衝片段
    if not is_final:
        from .toolkits.redis_store import append_audio_segment  # 延遲載入避免循環

        append_audio_segment(user_id, audio_id, query)
        return "👌 已收到語音片段"

    # 2) 音檔級鎖：一次且只一次處理同一段音檔
    lock_id = f"{user_id}#audio:{audio_id}"
    # 使用獨立的輕量鎖，避免與其他 session state 衝突
    # P0-1: 增加 TTL 到 180 秒，避免長語音處理時鎖過期
    if not acquire_audio_lock(lock_id, ttl_sec=180):
        cached = get_audio_result(user_id, audio_id)
        return cached or "我正在處理你的語音，請稍等一下喔。"

    try:
        # 3) 合併之前緩衝的 partial → 最終要處理的全文
        head = read_and_clear_audio_segments(user_id, audio_id)
        full_text = (head + " " + query).strip() if head else query

        # 4) 先 guardrail，再 health agent
        os.environ["CURRENT_USER_ID"] = user_id

        # 優先用 CrewAI；失敗則 fallback 自行判斷
        try:
            guard = agent_manager.get_guardrail()
            guard_task = Task(
                description=(
                    f"判斷是否需要攔截：「{full_text}」。"
                    "務必使用 model_guardrail 工具進行判斷；"
                    "安全回 OK；需要攔截時回 BLOCK: <原因>（僅此兩種）。"
                ),
                expected_output="OK 或 BLOCK: <原因>",
                agent=guard,
            )
            guard_res = (
                Crew(agents=[guard], tasks=[guard_task], verbose=False).kickoff().raw
                or ""
            ).strip()
        except Exception:
            guard_res = ModelGuardrailTool()._run(full_text)

            # 只保留攔截與否
        is_block = guard_res.startswith("BLOCK:")
        block_reason = guard_res[6:].strip() if is_block else ""
        
        print(f"🛡️ Guardrail 檢查結果: {'BLOCK' if is_block else 'OK'} - 查詢: '{full_text[:50]}...'")
        if is_block:
            print(f"🚫 攔截原因: {block_reason}")

        # 產生最終回覆：優先用 CrewAI；失敗則 fallback OpenAI + Milvus 查詢
        try:
            care = agent_manager.get_health_agent(user_id)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # P0-3: BLOCK 分支直接跳過記憶/RAG 檢索，節省成本
            if is_block:
                ctx = ""  # 不檢索記憶
                print("⚠️ 因安全檢查攔截，跳過記憶檢索")
            else:
                ctx = build_prompt_from_redis(user_id, line_user_id=line_user_id, k=6, current_input=full_text)
            task_description = COMPANION_PROMPT_TEMPLATE.format(
                now=now_str,
                ctx=ctx or "無", # 確保 ctx 不是空字串
                query=full_text
            )
            task = Task(
                description=task_description,
                expected_output="一句極其簡潔、自然、口語化、像家人一樣的回應。",
                agent=care,
            )
            # task = Task(
            #     description=(
            #         f"{ctx}\n\n使用者輸入：{full_text}\n"
            #         "請以『國民孫女』口吻回覆，遵守【回覆風格規則】：禁止列點、不要用數字或符號開頭、避免學術式摘要；台語混中文、自然聊天感。"
            #         + (
            #             "\n【安全政策—必須婉拒】此輸入被安全檢查判定為超出能力範圍（例如違法、成人內容、醫療/用藥/劑量/診斷等具體指示）。"
            #             "請直接婉拒，**不要**提供任何具體方案、診斷或劑量，也**不要**硬給替代作法。"
            #             "僅可給一般層級的安全提醒（如：鼓勵諮詢合格醫師/藥師）與情緒安撫的一兩句話。"
            #             if is_block
            #             else "\n【正常回覆】若內容屬一般衛教/日常關懷，簡短回應並可給 1–2 個小步驟建議。"
            #         )
            #     ),
            #     expected_output="台語風格的溫暖關懷回覆，必要時使用工具。",
            #     agent=care,
            # )
            res = Crew(agents=[care], tasks=[task], verbose=False).kickoff().raw or ""
        except Exception:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("MODEL_NAME", "gpt-4o-mini")
            if is_block:
                # P0-3: BLOCK 分支跳過記憶/RAG 檢索
                sys = "你是會講台語的健康陪伴者。當輸入被判為超出能力範圍時，必須婉拒且不可提供具體方案/診斷/劑量，只能一般性提醒就醫。語氣溫暖、不列點。"
                user_msg = f"此輸入被判為超出能力範圍（{block_reason or '安全風險'}）。請用台語溫柔婉拒，不提供任何具體建議或替代作法，只做一般安全提醒與情緒安撫 1–2 句。"
                res_obj = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": sys},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.2,
                )
                res = (res_obj.choices[0].message.content or "").strip()
            else:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ctx = build_prompt_from_redis(user_id, k=6, current_input=full_text)
                qa = SearchMilvusTool()._run(full_text)
                sys = "你是會講台語的健康陪伴者，語氣溫暖務實，避免醫療診斷與劑量指示。必要時提醒就醫。"
                full_ctx = ctx
                if qa and qa != '[查無高相似度結果]':
                    full_ctx += f"\n\n[相關檢索資訊]:\n{qa}"

                prompt = COMPANION_PROMPT_TEMPLATE.format(
                    now=now_str,
                    ctx=full_ctx,
                    query=full_text
                )
                # prompt = (
                #     f"{ctx}\n\n相關資料（可能空）：\n{qa}\n\n"
                #     f"使用者輸入：{full_text}\n請以台語風格回覆；結尾給一段溫暖鼓勵。"
                # )
                res_obj = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": sys},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.5,
                )
                res = (res_obj.choices[0].message.content or "").strip()
        # 5) 結果快取 + 落歷史
        set_audio_result(user_id, audio_id, res)
        log_session(user_id, full_text, res, line_user_id=line_user_id) # 【新增】傳遞 line_user_id
        return res

    finally:
        release_audio_lock(lock_id)
