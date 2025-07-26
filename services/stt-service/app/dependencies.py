from app.core.stt_service import STTService, get_stt_service

def get_service() -> STTService:
    """
    Dependency injector for the STTService.
    This can be overridden in tests.
    """
    return get_stt_service()
