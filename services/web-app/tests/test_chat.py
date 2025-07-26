import pytest
from unittest.mock import MagicMock

def test_post_to_chat_api_publishes_task(client, mocker):
    """
    Tests that POST /api/v1/chat/text correctly publishes a task to RabbitMQ.
    """
    # Mock the RabbitMQ service
    mock_rabbitmq_service = MagicMock()
    
    # Use mocker to patch the get_rabbitmq_service function
    mocker.patch(
        'app.api.chat.get_rabbitmq_service', 
        return_value=mock_rabbitmq_service
    )
    
    # The data we'll send to the API
    test_data = {
        "patient_id": 1,
        "text": "Hello from the test!"
    }
    
    # Call the API endpoint
    response = client.post('/api/v1/chat/text', json=test_data)
    
    # Assert the API response is successful
    assert response.status_code == 202 # 202 Accepted is a good choice for async tasks
    
    # Assert that the publish_message method was called once
    mock_rabbitmq_service.publish_message.assert_called_once()
    
    # Assert it was called with the correct arguments
    args, kwargs = mock_rabbitmq_service.publish_message.call_args
    assert kwargs['queue_name'] == 'text_processing_queue' # Check queue name
    assert kwargs['message_body']['patient_id'] == test_data['patient_id']
    assert kwargs['message_body']['text'] == test_data['text']

def test_post_audio_publishes_task(client, mocker):
    """
    Tests that POST /api/v1/chat/audio:
    1. Calls MinIO service to get a presigned URL.
    2. Publishes a task to the audio processing queue.
    3. Returns the presigned URL to the client.
    """
    # 1. Mock external services
    mock_rabbitmq_service = MagicMock()
    mock_minio_service = MagicMock()
    
    # Mock the return value for the presigned URL
    presigned_url_data = {
        "url": "http://fake-minio-url.com/upload-here",
        "object_name": "unique-audio-file.wav"
    }
    mock_minio_service.generate_presigned_upload_url.return_value = presigned_url_data
    
    # Patch the service getters
    mocker.patch('app.api.chat.get_rabbitmq_service', return_value=mock_rabbitmq_service)
    # Patch the minio_service where it's used (in the chat API module)
    mock_minio_generate = mocker.patch('app.api.chat.minio_service.generate_presigned_upload_url', return_value=presigned_url_data)
    
    # 2. Prepare request data
    request_data = {
        "patient_id": 2,
        "filename": "patient-audio.wav"
    }
    
    # 3. Call the API endpoint
    response = client.post('/api/v1/chat/audio', json=request_data)
    
    # 4. Assertions
    assert response.status_code == 202
    
    # Assert MinIO service was called correctly
    mock_minio_generate.assert_called_once_with(
        bucket_name='audio-uploads',
        object_name=request_data['filename']
    )
    
    # Assert RabbitMQ service was called correctly
    mock_rabbitmq_service.publish_message.assert_called_once()
    args, kwargs = mock_rabbitmq_service.publish_message.call_args
    assert kwargs['queue_name'] == 'audio_processing_queue'
    assert kwargs['message_body']['patient_id'] == request_data['patient_id']
    assert kwargs['message_body']['object_name'] == presigned_url_data['object_name']
    
    # Assert the response contains the presigned URL data
    assert response.json['data'] == presigned_url_data