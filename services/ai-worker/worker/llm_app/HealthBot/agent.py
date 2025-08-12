from crewai import Agent
from ..toolkits.tools import (
    SearchMilvusTool,
    AlertCaseManagerTool,
    summarize_chunk_and_commit,
    ModelGuardrailTool,
)
from ..toolkits.redis_store import (
    fetch_unsummarized_tail,
    fetch_all_history,
    get_summary,
    peek_next_n,
    peek_remaining,
    set_state_if,
    purge_user_session,
)
from openai import OpenAI
import os
from pymilvus import connections
try:
    from pymilvus import utility  # type: ignore
except Exception:  # pragma: no cover
    utility = None
from ..embedding import safe_to_vector
import time


STM_MAX_CHARS = int(os.getenv("STM_MAX_CHARS", 1800))
SUMMARY_MAX_CHARS = int(os.getenv("SUMMARY_MAX_CHARS", 3000))
REFINE_CHUNK_ROUNDS = int(os.getenv("REFINE_CHUNK_ROUNDS", 20))
SUMMARY_CHUNK_SIZE = int(os.getenv("SUMMARY_CHUNK_SIZE", 5))


def _shrink_tail(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    idx = tail.find("--- ")
    return tail[idx:] if idx != -1 else tail


def build_prompt_from_redis(user_id: str, k: int = 6, current_input: str = "") -> str:
    summary, _ = get_summary(user_id)
    summary = _shrink_tail(summary, SUMMARY_MAX_CHARS) if summary else ""
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
    if summary:
        parts.append("📌 歷史摘要：\n" + summary)
    if chat:
        parts.append("🕓 近期對話（未摘要）：\n" + chat)
    if current_input:
        qv = safe_to_vector(current_input)
        # 這裡省略記憶檢索部分以降低依賴
    return "\n\n".join(parts)


def create_guardrail_agent() -> Agent:
    return Agent(
        role="風險檢查員",
        goal="攔截違法/危險/自傷/需專業人士之具體指導內容",
        backstory="你是系統第一道安全防線，只輸出嚴格判斷結果。",
        tools=[ModelGuardrailTool()],
        memory=False,
        verbose=False,
    )


def create_health_companion(user_id: str) -> Agent:
    return Agent(
        role="健康陪伴者",
        goal="以台語關懷長者健康與心理狀況，必要時通報",
        backstory="你是會講台語的金孫型陪伴機器人，回覆溫暖務實。",
        tools=[SearchMilvusTool(), AlertCaseManagerTool()],
        memory=True,
        verbose=False,
    )


