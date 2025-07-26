from fastapi import UploadFile

class STTService:
    async def transcribe_audio(self, audio_file: UploadFile) -> str:
        """
        Transcribes the given audio file.
        This is a placeholder implementation.
        """
        # 實際的 STT 模型呼叫邏輯會在這裡
        # 為了測試，我們先假設它回傳檔案名稱
        return f"transcribed_{audio_file.filename}"

_stt_service_instance = STTService()

def get_stt_service() -> STTService:
    """Factory function to get the STTService instance."""
    return _stt_service_instance
