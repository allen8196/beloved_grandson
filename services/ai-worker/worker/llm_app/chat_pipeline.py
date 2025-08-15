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


def log_session(user_id: str, query: str, reply: str, request_id: Optional[str] = None):
    rid = request_id or make_request_id(user_id, query)
    if not try_register_request(user_id, rid):
        # 去重，跳過重複請求
        return
    append_round(user_id, {"input": query, "output": reply, "rid": rid})
    # 嘗試抓下一段 5 輪（不足會回空）→ LLM 摘要 → CAS 提交
    start, chunk = peek_next_n(user_id, SUMMARY_CHUNK_SIZE)
    if start is not None and chunk:
        summarize_chunk_and_commit(user_id, start_round=start, history_chunk=chunk)


def handle_user_message(
    agent_manager: AgentManager,
    user_id: str,
    query: str,
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

        # 產生最終回覆：優先用 CrewAI；失敗則 fallback OpenAI + Milvus 查詢
        try:
            care = agent_manager.get_health_agent(user_id)

            # P0-3: BLOCK 分支直接跳過記憶/RAG 檢索，節省成本
            if is_block:
                ctx = ""  # 不檢索記憶
            else:
                ctx = build_prompt_from_redis(user_id, k=6, current_input=full_text)

            task = Task(
                description=(
                    f"{ctx}\n\n使用者輸入：{full_text}\n"
                    "請以『國民孫女』口吻回覆，遵守【回覆風格規則】：禁止列點、不要用數字或符號開頭、避免學術式摘要；台語混中文、自然聊天感。"
                    + (
                        "\n【安全政策—必須婉拒】此輸入被安全檢查判定為超出能力範圍（例如違法、成人內容、醫療/用藥/劑量/診斷等具體指示）。"
                        "請直接婉拒，**不要**提供任何具體方案、診斷或劑量，也**不要**硬給替代作法。"
                        "僅可給一般層級的安全提醒（如：鼓勵諮詢合格醫師/藥師）與情緒安撫的一兩句話。"
                        if is_block
                        else "\n【正常回覆】若內容屬一般衛教/日常關懷，簡短回應並可給 1–2 個小步驟建議。"
                    )
                ),
                expected_output="台語風格的溫暖關懷回覆，必要時使用工具。",
                agent=care,
            )
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
                ctx = build_prompt_from_redis(user_id, k=6, current_input=full_text)
                qa = SearchMilvusTool()._run(full_text)
                sys = "你是會講台語的健康陪伴者，語氣溫暖務實，避免醫療診斷與劑量指示。必要時提醒就醫。"
                prompt = (
                    f"{ctx}\n\n相關資料（可能空）：\n{qa}\n\n"
                    f"使用者輸入：{full_text}\n請以台語風格回覆；結尾給一段溫暖鼓勵。"
                )
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
        log_session(user_id, full_text, res)
        return res

    finally:
        release_audio_lock(lock_id)
