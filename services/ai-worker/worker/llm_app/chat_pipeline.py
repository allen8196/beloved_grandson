import os
import hashlib
from typing import Optional

from crewai import Crew, Task

from .HealthBot.agent import (
    create_guardrail_agent,
    create_health_companion,
    build_prompt_from_redis,
)
from .toolkits.redis_store import (
    try_register_request,
    make_request_id,
    append_round,
    peek_next_n,
    read_and_clear_audio_segments,
    get_audio_result,
    set_audio_result,
    set_state_if,
    xadd_alert,
    acquire_audio_lock,
    release_audio_lock,
)
from .toolkits.tools import summarize_chunk_and_commit, SearchMilvusTool, ModelGuardrailTool
from openai import OpenAI


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


def handle_user_message(agent_manager: AgentManager, user_id: str, query: str,
                        audio_id: Optional[str] = None, is_final: bool = True) -> str:
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
    if not acquire_audio_lock(lock_id, ttl_sec=30):
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
            guard_res = (Crew(agents=[guard], tasks=[guard_task], verbose=False).kickoff().raw or "").strip()
        except Exception:
            guard_res = ModelGuardrailTool()._run(full_text)
        if guard_res.startswith("BLOCK:"):
            reason = guard_res[6:].strip()
            if any(k in reason for k in ["自傷", "自殺", "傷害自己", "緊急"]):
                xadd_alert(user_id=user_id, reason=f"可能自傷風險：{full_text}", severity="high")
            reply = "抱歉，這個問題涉及違規或需專業人士評估，我無法提供解答。"
            set_audio_result(user_id, audio_id, reply)
            log_session(user_id, full_text, reply)
            return reply

        # 產生最終回覆：優先用 CrewAI；失敗則 fallback OpenAI + Milvus 查詢
        try:
            care = agent_manager.get_health_agent(user_id)
            ctx = build_prompt_from_redis(user_id, k=6, current_input=full_text)
            task = Task(
                description=(
                    f"{ctx}\n\n使用者輸入：{full_text}\n請以台語風格溫暖務實回覆；"
                    "有需要查看COPD相關資料或緊急事件需要通報時，請使用工具。"
                ),
                expected_output="台語風格的溫暖關懷回覆，必要時使用工具。",
                agent=care,
            )
            res = (Crew(agents=[care], tasks=[task], verbose=False).kickoff().raw or "")
        except Exception:
            ctx = build_prompt_from_redis(user_id, k=6, current_input=full_text)
            qa = SearchMilvusTool()._run(full_text)
            sys = "你是會講台語的健康陪伴者，語氣溫暖務實，避免醫療診斷與劑量指示。必要時提醒就醫。"
            prompt = (
                f"{ctx}\n\n相關資料（可能空）：\n{qa}\n\n"
                f"使用者輸入：{full_text}\n請以台語風格回覆；條列要點，結尾給一段溫暖鼓勵。"
            )
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("MODEL_NAME", "gpt-4o-mini")
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


