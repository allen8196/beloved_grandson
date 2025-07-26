import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from app.main import app
from app.dependencies import get_service

client = TestClient(app)

@pytest.fixture
def mock_stt_service():
    service = MagicMock()
    # Since transcribe_audio is an async function, we use AsyncMock
    service.transcribe_audio = AsyncMock(return_value="mocked transcription")
    return service

def test_transcribe_calls_stt_service(mock_stt_service):
    """
    Tests that the /api/v1/transcribe endpoint calls the STTService.
    """
    app.dependency_overrides[get_service] = lambda: mock_stt_service
    
    files = {'audio_file': ('test.wav', b'fake-audio-data', 'audio/wav')}
    response = client.post("/api/v1/transcribe", files=files)
    
    assert response.status_code == 200
    # Check that the mocked service was called
    mock_stt_service.transcribe_audio.assert_called_once()
    # Check the response contains the mocked transcription
    assert response.json()['transcribed_text'] == "mocked transcription"
    
    app.dependency_overrides.clear()

def test_transcribe_endpoint_exists():
    """
    Tests if the /api/v1/transcribe endpoint exists.
    """
    files = {'audio_file': ('test.wav', b'fake-audio-data', 'audio/wav')}
    response = client.post("/api/v1/transcribe", files=files)
    assert response.status_code != 404
    assert response.status_code == 200

def test_transcribe_requires_audio_file():
    """
    Tests if the endpoint returns 422 if no audio file is provided.
    """
    response = client.post("/api/v1/transcribe")
    assert response.status_code == 422
