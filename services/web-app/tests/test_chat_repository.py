# F:\iSpan_project\services\web-app\tests\test_chat_repository.py
import pytest
from app.core.chat_repository import ChatRepository
from app.extensions import get_db
from datetime import datetime
from bson import ObjectId

@pytest.fixture(scope='module')
def chat_repo():
    """Fixture to provide a ChatRepository instance."""
    return ChatRepository()

@pytest.fixture(scope='function', autouse=True)
def cleanup_db(chat_repo):
    """Fixture to clean up the database after each test."""
    yield
    # Clean up logic
    db = get_db()
    db.conversations.delete_many({})
    db.chat_messages.delete_many({})

def test_create_conversation(chat_repo):
    """
    Test case for creating a new conversation.
    """
    patient_id = 1
    therapist_id = 2
    
    conversation_id = chat_repo.create_conversation(patient_id, therapist_id)
    
    assert conversation_id is not None
    assert isinstance(conversation_id, ObjectId)
    
    # Verify the document was inserted correctly
    db = get_db()
    convo = db.conversations.find_one({"_id": conversation_id})
    
    assert convo is not None
    assert convo['patient_id'] == patient_id
    assert convo['therapist_id'] == therapist_id
    assert 'start_time' in convo
    assert isinstance(convo['start_time'], datetime)

def test_add_chat_message(chat_repo):
    """
    Test case for adding a new chat message to a conversation.
    """
    # First, create a conversation to add a message to
    conversation_id = chat_repo.create_conversation(patient_id=1, therapist_id=2)
    
    message_data = {
        "conversation_id": conversation_id,
        "sender_type": "user",
        "content": "Hello, this is a test message.",
        "audio_url": "s3://bucket/audio.mp3"
    }
    
    message_id = chat_repo.add_chat_message(message_data)
    
    assert message_id is not None
    assert isinstance(message_id, ObjectId)
    
    # Verify the document was inserted correctly
    db = get_db()
    msg = db.chat_messages.find_one({"_id": message_id})
    
    assert msg is not None
    assert msg['conversation_id'] == conversation_id
    assert msg['sender_type'] == "user"
    assert msg['content'] == "Hello, this is a test message."
    assert msg['audio_url'] == "s3://bucket/audio.mp3"
    assert 'timestamp' in msg
    assert isinstance(msg['timestamp'], datetime)


def test_get_conversations_by_patient_id(chat_repo):
    """
    Test case for retrieving conversations for a specific patient.
    """
    # Create conversations for two different patients
    chat_repo.create_conversation(patient_id=1)
    chat_repo.create_conversation(patient_id=1)
    chat_repo.create_conversation(patient_id=2)
    
    conversations = chat_repo.get_conversations_by_patient_id(patient_id=1)
    
    assert len(conversations) == 2
    for convo in conversations:
        assert convo['patient_id'] == 1
        assert isinstance(convo['_id'], str) # Should be serialized

def test_get_messages_by_conversation_id(chat_repo):
    """
    Test case for retrieving messages for a specific conversation.
    """
    conv_id_1 = chat_repo.create_conversation(patient_id=1)
    conv_id_2 = chat_repo.create_conversation(patient_id=1)
    
    # Add messages to both conversations
    chat_repo.add_chat_message({"conversation_id": conv_id_1, "content": "Message 1 for convo 1"})
    chat_repo.add_chat_message({"conversation_id": conv_id_1, "content": "Message 2 for convo 1"})
    chat_repo.add_chat_message({"conversation_id": conv_id_2, "content": "Message 1 for convo 2"})
    
    messages = chat_repo.get_messages_by_conversation_id(str(conv_id_1))
    
    assert len(messages) == 2
    for msg in messages:
        assert msg['conversation_id'] == str(conv_id_1)
        assert isinstance(msg['_id'], str) # Should be serialized

def test_find_conversation_by_id(chat_repo):
    """
    Test case for finding a single conversation by its ID.
    """
    conv_id = chat_repo.create_conversation(patient_id=1)
    
    conversation = chat_repo.find_conversation_by_id(str(conv_id))
    
    assert conversation is not None
    assert conversation['_id'] == conv_id
    assert conversation['patient_id'] == 1

def test_find_conversation_by_id_not_found(chat_repo):
    """
    Test case for finding a non-existent conversation.
    """
    non_existent_id = "60c72b2f9b1e8b3b2c8b4567"
    conversation = chat_repo.find_conversation_by_id(non_existent_id)
    
    assert conversation is None

# --- Database Error Handling Tests (T-7.3.4) ---
from pymongo.errors import PyMongoError

def test_create_conversation_db_error(chat_repo, mocker):
    """Test create_conversation handles PyMongoError."""
    mocker.patch.object(chat_repo.conversations_collection, 'insert_one', side_effect=PyMongoError("DB Connection Error"))
    result = chat_repo.create_conversation(patient_id=1)
    assert result is None

def test_add_chat_message_db_error(chat_repo, mocker):
    """Test add_chat_message handles PyMongoError."""
    mocker.patch.object(chat_repo.messages_collection, 'insert_one', side_effect=PyMongoError("DB Connection Error"))
    result = chat_repo.add_chat_message({"content": "test"})
    assert result is None

def test_get_conversations_db_error(chat_repo, mocker):
    """Test get_conversations_by_patient_id handles PyMongoError."""
    mocker.patch.object(chat_repo.conversations_collection, 'find', side_effect=PyMongoError("DB Connection Error"))
    result = chat_repo.get_conversations_by_patient_id(patient_id=1)
    assert result == []

def test_get_messages_db_error(chat_repo, mocker):
    """Test get_messages_by_conversation_id handles PyMongoError."""
    mocker.patch.object(chat_repo.messages_collection, 'find', side_effect=PyMongoError("DB Connection Error"))
    result = chat_repo.get_messages_by_conversation_id(conversation_id=str(ObjectId()))
    assert result == []

def test_find_conversation_db_error(chat_repo, mocker):
    """Test find_conversation_by_id handles PyMongoError."""
    mocker.patch.object(chat_repo.conversations_collection, 'find_one', side_effect=PyMongoError("DB Connection Error"))
    result = chat_repo.find_conversation_by_id(conversation_id=str(ObjectId()))
    assert result is None

