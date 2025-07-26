import pytest
import json
from unittest.mock import MagicMock, call
from worker.main import process_text_task, process_audio_task, publish_notification

def test_process_text_task_calls_llm_service(mocker):
    """
    Tests that process_text_task correctly calls the llm-service.
    """
    # 模擬 requests.post
    mock_post = mocker.patch("requests.post")
    
    # 定義 llm-service 的 URL
    llm_service_url = "http://llm-service:8000/api/v1/chat"
    
    # 測試的訊息
    test_message = "Hello, AI!"
    
    # 呼叫我們要測試的函式
    process_text_task(test_message)
    
    # 斷言 requests.post 被呼叫了一次，且包含 timeout 參數
    mock_post.assert_called_once_with(
        llm_service_url,
        json={"text": test_message},
        timeout=10
    )

def test_process_audio_task_full_pipeline_and_notifies(mocker):
    """
    Tests that process_audio_task correctly calls all services and publishes a notification.
    """
    # 1. Mock all external dependencies
    mocker.patch('boto3.client')
    mock_post = mocker.patch("requests.post")
    mock_publish = mocker.patch("worker.main.publish_notification")

    # Simulate service responses
    mock_stt_response = MagicMock()
    mock_stt_response.json.return_value = {"transcribed_text": "Hello from STT"}
    mock_llm_response = MagicMock()
    mock_llm_response.json.return_value = {"response": "Hello from LLM"}
    mock_tts_response = MagicMock()
    mock_tts_response.json.return_value = {"audio_url": "http://minio/audio/response.wav"}
    mock_post.side_effect = [mock_stt_response, mock_llm_response, mock_tts_response]

    # 2. Call the function
    process_audio_task("audio-uploads", "test.wav")

    # 3. Assert that the notification was published with the correct data
    expected_notification = {
        "status": "completed",
        "original_file": "test.wav",
        "transcribed_text": "Hello from STT",
        "llm_response": "Hello from LLM",
        "tts_output_url": "http://minio/audio/response.wav"
    }
    mock_publish.assert_called_once_with(expected_notification)

def test_publish_notification(mocker):
    """
    Tests that the publish_notification function correctly calls the pika library.
    """
    mock_pika = mocker.patch("pika.BlockingConnection")
    mock_connection = MagicMock()
    mock_channel = MagicMock()
    mock_pika.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel

    test_message = {"key": "value"}
    publish_notification(test_message)

    mock_channel.queue_declare.assert_called_once_with(queue="notifications_queue", durable=True)
    mock_channel.basic_publish.assert_called_once_with(
        exchange='',
        routing_key="notifications_queue",
        body=json.dumps(test_message),
        properties=mocker.ANY  # We don't need to inspect the properties object in detail
    )
    mock_connection.close.assert_called_once()
