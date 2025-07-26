from fastapi import APIRouter, Depends, UploadFile, File
from app.core.stt_service import STTService
from app.dependencies import get_service

router = APIRouter()

@router.post("/transcribe")
async def transcribe_endpoint(
    audio_file: UploadFile = File(...),
    service: STTService = Depends(get_service)
):
    """
    Handles audio transcription requests by calling the STTService.
    """
    transcribed_text = await service.transcribe_audio(audio_file)
    return {"filename": audio_file.filename, "transcribed_text": transcribed_text}
