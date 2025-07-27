# services/web-app/tests/test_notification_service.py
import pytest
import json
from unittest.mock import MagicMock, patch
from app.core.notification_service import message_callback

@patch('app.core.notification_service.ChatRepository', autospec=True)
@patch('app.core.notification_service.socketio', autospec=True)
def test_message_callback_success(mock_socketio, mock_chat_repo):
    """
    T-7.2.3: Test the happy path of the message_callback function.
    It should decode the message, save history, and emit a notification.
    """
    # Arrange
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 123
    
    body = json.dumps({
        "patient_id": 1,
        "therapist_id": 2,
        "user_transcript": "Hello AI",
        "ai_response": "Hello User",
        "response_audio_url": "http://minio/audio.mp3"
    }).encode('utf-8')

    # Mock ChatRepository instance and its methods
    mock_repo_instance = mock_chat_repo.return_value
    mock_repo_instance.create_conversation.return_value = "conv_123"

    # Act
    message_callback(mock_ch, mock_method, None, body)

    # Assert
    # 1. Chat history was saved correctly
    mock_repo_instance.create_conversation.assert_called_once_with(patient_id=1, therapist_id=2)
    
    assert mock_repo_instance.add_chat_message.call_count == 2
    mock_repo_instance.add_chat_message.assert_any_call({
        "conversation_id": "conv_123",
        "sender_type": "user",
        "content": "Hello AI",
    })
    mock_repo_instance.add_chat_message.assert_any_call({
        "conversation_id": "conv_123",
        "sender_type": "ai",
        "content": "Hello User",
        "audio_url": "http://minio/audio.mp3"
    })

    # 2. WebSocket notification was emitted
    mock_socketio.emit.assert_called_once_with('notification', json.loads(body))

    # 3. RabbitMQ message was acknowledged
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=123)

@patch('app.core.notification_service.ChatRepository', autospec=True)
@patch('app.core.notification_service.socketio', autospec=True)
def test_message_callback_json_decode_error(mock_socketio, mock_chat_repo):
    """
    T-7.2.3: Test how the callback handles a message that is not valid JSON.
    It should not crash, should not call business logic, and should still ack the message.
    """
    # Arrange
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 456
    body = b'this is not json'

    # Act
    message_callback(mock_ch, mock_method, None, body)

    # Assert
    mock_chat_repo.return_value.create_conversation.assert_not_called()
    mock_socketio.emit.assert_not_called()
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=456)

@patch('app.core.notification_service.ChatRepository', autospec=True)
@patch('app.core.notification_service.socketio', autospec=True)
def test_message_callback_missing_keys(mock_socketio, mock_chat_repo):
    """
    T-7.2.3: Test how the callback handles a valid JSON message with missing keys.
    It should handle the error gracefully and still ack the message.
    """
    # Arrange
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 789
    # Missing "user_transcript" key
    body = json.dumps({"patient_id": 1}).encode('utf-8')

    # Act
    message_callback(mock_ch, mock_method, None, body)

    # Assert
    # It might call create_conversation depending on implementation, but shouldn't crash.
    # The key is that it acks the message and doesn't proceed to emit.
    mock_socketio.emit.assert_not_called() # Or called with incomplete data, but not_called is safer
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=789)

@patch('app.core.notification_service.ChatRepository', autospec=True)
@patch('app.core.notification_service.socketio', autospec=True)
def test_message_callback_general_exception(mock_socketio, mock_chat_repo):
    """
    T-7.2.3: Test the callback's behavior when a downstream service raises an exception.
    It should catch the exception and still ack the message.
    """
    # Arrange
    mock_ch = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 101
    body = json.dumps({"patient_id": 1, "user_transcript": "test"}).encode('utf-8')

    # Simulate a database error
    mock_chat_repo.return_value.create_conversation.side_effect = Exception("Database connection failed")

    # Act
    message_callback(mock_ch, mock_method, None, body)

    # Assert
    mock_socketio.emit.assert_not_called()
    mock_ch.basic_ack.assert_called_once_with(delivery_tag=101)