# F:\iSpan_project\services\web-app\tests\test_chat_api.py
import pytest
from unittest.mock import patch
from app.models import User

def test_get_conversations_returns_404_for_nonexistent_patient(client, db):
    """
    Test that GET /api/v1/patients/<patient_id>/conversations returns 404
    for a patient that does not exist.
    """
    # The `db` fixture ensures the tables are created.
    # We assume patient with ID 999 does not exist.
    response = client.get('/api/v1/patients/999/conversations')
    assert response.status_code == 404

@patch('app.api.chat.ChatRepository')
def test_get_conversations_returns_empty_list(MockChatRepository, client, db, session):
    """
    Test that the endpoint returns an empty list for a user with no conversations.
    """
    # Arrange
    # 1. Create a patient in the test database
    patient = User(id=1, account='testpatient', password_hash='password', is_staff=False)
    session.add(patient)
    session.commit()

    # 2. Mock the ChatRepository
    mock_repo_instance = MockChatRepository.return_value
    mock_repo_instance.get_conversations_by_patient_id.return_value = []
    
    # Act
    response = client.get('/api/v1/patients/1/conversations')
    
    # Assert
    assert response.status_code == 200
    assert response.json == []
    mock_repo_instance.get_conversations_by_patient_id.assert_called_once_with(patient_id=1)

def test_get_messages_returns_404_for_nonexistent_conversation(client):
    """
    Test GET /api/v1/conversations/<conversation_id>/messages returns 404
    for a conversation that does not exist.
    """
    # A valid BSON ObjectId string that likely doesn't exist
    non_existent_id = "60c72b9f9b1e8b3b3c9d8e1a"
    response = client.get(f'/api/v1/conversations/{non_existent_id}/messages')
    assert response.status_code == 404

@patch('app.api.chat.ChatRepository')
def test_get_messages_returns_empty_list(MockChatRepository, client):
    """
    Test that the endpoint returns an empty list for a conversation with no messages.
    """
    # Arrange
    mock_repo_instance = MockChatRepository.return_value
    mock_repo_instance.get_messages_by_conversation_id.return_value = []
    
    # Act
    conversation_id = "60c72b9f9b1e8b3b3c9d8e1b" # A valid, existing ID
    response = client.get(f'/api/v1/conversations/{conversation_id}/messages')
    
    # Assert
    assert response.status_code == 200
    assert response.json == []
    mock_repo_instance.get_messages_by_conversation_id.assert_called_once_with(conversation_id=conversation_id)

