import pytest
from unittest.mock import MagicMock, ANY
import json

# 匯入我們要直接觸發的 callback 函式
from app.core.notification_service import message_callback as notification_callback

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
        "patient_id": "patient_test_01",
        "text": "Hello from the test!"
    }

    # Call the API endpoint
    response = client.post('/api/v1/chat/text', json=test_data)

    # Assert the API response is successful
    assert response.status_code == 202

    # Assert that the publish_message method was called once
    mock_rabbitmq_service.publish_message.assert_called_once()

    # Assert it was called with the correct arguments
    args, kwargs = mock_rabbitmq_service.publish_message.call_args
    assert kwargs['message_body']['patient_id'] == test_data['patient_id']
    assert kwargs['message_body']['text'] == test_data['text']

def test_post_audio_publishes_task(client, mocker):
    """
    Tests that POST /api/v1/chat/audio publishes a task correctly.
    """
    # 1. Mock external services
    mock_rabbitmq_service = MagicMock()
    mocker.patch('app.api.chat.get_rabbitmq_service', return_value=mock_rabbitmq_service)

    # 2. Prepare request data
    request_data = {
        "patient_id": "patient_test_02",
        "filename": "patient-audio.wav"
    }

    # 3. Call the API endpoint
    response = client.post('/api/v1/chat/audio', json=request_data)

    # 4. Assertions
    assert response.status_code == 202

    # Assert RabbitMQ service was called correctly
    mock_rabbitmq_service.publish_message.assert_called_once()
    args, kwargs = mock_rabbitmq_service.publish_message.call_args

    expected_message_body = {
        'patient_id': request_data['patient_id'],
        'object_name': request_data['filename'],
        'bucket_name': 'audio-uploads'
    }
    assert kwargs['message_body'] == expected_message_body

    # Assert the response contains the data sent to the queue
    assert response.json['data'] == expected_message_body

def test_notification_is_broadcast_via_websocket(socketio_client):
    """
    T-6.9.1: Tests that a message consumed from RabbitMQ is broadcast via WebSocket.
    """
    # 1. Connect the test client
    assert socketio_client.is_connected()

    # 2. Prepare a mock notification message
    notification_data = {
        "patient_id": 1,
        "therapist_id": 2,
        "user_transcript": "This is a test transcript.",
        "ai_response": "This is a test AI response.",
        "response_audio_url": "http://minio/audio/response.wav",
        "status": "completed"
    }
    notification_body = json.dumps(notification_data).encode('utf-8')

    # 3. Mock the arguments that the pika callback expects
    mock_channel = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 123
    mock_properties = MagicMock()

    # 4. Directly call the callback function to simulate a message from RabbitMQ
    notification_callback(mock_channel, mock_method, mock_properties, notification_body)

    # 5. Get events received by the client
    received_events = socketio_client.get_received()

    # 6. Assertions
    assert len(received_events) == 1

    event = received_events[0]
    assert event['name'] == 'notification'
    assert len(event['args']) == 1
    assert event['args'][0] == notification_data

    # Assert that basic_ack was called to acknowledge the message
    mock_channel.basic_ack.assert_called_once_with(delivery_tag=mock_method.delivery_tag)


def test_notification_callback_handles_invalid_json(mocker):
    """
    Tests that the notification callback handles malformed JSON gracefully.
    """
    # Mock the logger to spy on it
    mock_logger = mocker.patch('app.core.notification_service.logging.error')
    
    # Prepare a malformed message
    invalid_body = b'{"key": "value",}' # Invalid JSON due to trailing comma

    # Mock pika arguments
    mock_channel = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 456

    # Call the callback
    notification_callback(mock_channel, mock_method, None, invalid_body)

    # Assert that an error was logged
    mock_logger.assert_called_once()
    log_message = mock_logger.call_args[0][0]
    assert "Failed to decode JSON" in log_message

    # Assert that the message was still acknowledged to prevent requeue loops
    mock_channel.basic_ack.assert_called_once_with(delivery_tag=mock_method.delivery_tag)

from app.models.models import User


@pytest.fixture
def patient_user(session):
    """Creates a test patient user."""
    user = User(
        id=99,
        account='test_patient_for_chat',
        first_name='Chat',
        last_name='Patient',
        is_staff=False
    )
    user.set_password('password')
    session.add(user)
    session.commit()
    return user

# --- Chat API Error Handling and Edge Cases ---

def test_post_text_message_missing_fields(client):
    """Test POST /chat/text with missing fields returns 400."""
    response = client.post('/api/v1/chat/text', json={"patient_id": "123"})
    assert response.status_code == 400
    assert response.json['error']['code'] == 'INVALID_INPUT'

def test_post_text_message_publish_error(client, mocker):
    """Test POST /chat/text returns 500 when RabbitMQ publish fails."""
    mock_rabbitmq = MagicMock()
    mock_rabbitmq.publish_message.side_effect = Exception("Queue connection error")
    mocker.patch('app.api.chat.get_rabbitmq_service', return_value=mock_rabbitmq)

    response = client.post('/api/v1/chat/text', json={"patient_id": "123", "text": "hello"})
    assert response.status_code == 500
    assert response.json['error']['code'] == 'QUEUE_PUBLISH_ERROR'

def test_get_conversations_patient_not_found(client, session):
    """Test GET /conversations returns 404 for a non-existent patient."""
    response = client.get('/api/v1/patients/9999/conversations')
    assert response.status_code == 404

def test_get_conversations_repository_error(client, mocker, patient_user):
    """Test GET /conversations returns 500 when ChatRepository fails."""
    mocker.patch('app.api.chat.UserRepository.find_by_id', return_value=patient_user)
    mocker.patch('app.api.chat.ChatRepository.get_conversations_by_patient_id', side_effect=Exception("DB error"))
    
    response = client.get(f'/api/v1/patients/{patient_user.id}/conversations')
    assert response.status_code == 500
    assert response.json['error']['code'] == 'INTERNAL_SERVER_ERROR'

def test_get_messages_conversation_not_found(client):
    """Test GET /messages returns 404 for a non-existent conversation."""
    response = client.get('/api/v1/conversations/nonexistent123/messages')
    assert response.status_code == 404

def test_get_messages_repository_error(client, mocker):
    """Test GET /messages returns 500 when ChatRepository fails."""
    # We need to mock find_conversation_by_id to return something to avoid the first 404
    mocker.patch('app.api.chat.ChatRepository.find_conversation_by_id', return_value={"_id": "some_id"})
    mocker.patch('app.api.chat.ChatRepository.get_messages_by_conversation_id', side_effect=Exception("DB error"))
    
    response = client.get('/api/v1/conversations/some_id/messages')
    assert response.status_code == 500
    assert response.json['error']['code'] == 'INTERNAL_SERVER_ERROR'
