from app.core.llm_service import LLMService, get_llm_service

def get_service() -> LLMService:
    """
    Dependency injector for the LLMService.
    This can be overridden in tests.
    """
    return get_llm_service()
