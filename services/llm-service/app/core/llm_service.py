class LLMService:
    def generate_response(self, text: str) -> str:
        """
        Generates a response from the LLM.
        This is a placeholder implementation.
        """
        # 實際的 LLM 呼叫邏輯會在這裡
        return f"Echo: {text}"

_llm_service_instance = LLMService()

def get_llm_service() -> LLMService:
    """Factory function to get the LLMService instance."""
    return _llm_service_instance
