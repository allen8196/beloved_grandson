# F:\iSpan_project\services\web-app\app\core\chat_repository.py
import logging
from app.extensions import get_db
from datetime import datetime, timezone
from bson import ObjectId
from typing import Dict, Any, Optional, List
from pymongo.errors import PyMongoError

def _serialize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serializes a MongoDB document by converting ObjectId to string.
    """
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "conversation_id" in doc and isinstance(doc["conversation_id"], ObjectId):
        doc["conversation_id"] = str(doc["conversation_id"])
    return doc

class ChatRepository:
    """
    Repository for handling chat history data in MongoDB.
    """
    def __init__(self):
        self.db = get_db()
        self.conversations_collection = self.db.conversations
        self.messages_collection = self.db.chat_messages

    def create_conversation(self, patient_id: int, therapist_id: Optional[int] = None) -> Optional[ObjectId]:
        """
        Creates a new conversation session in the database.

        Args:
            patient_id: The ID of the patient.
            therapist_id: The ID of the therapist (optional).

        Returns:
            The ObjectId of the newly created conversation, or None on error.
        """
        try:
            now = datetime.now(timezone.utc)
            conversation_document = {
                "patient_id": patient_id,
                "therapist_id": therapist_id,
                "start_time": now,
                "created_at": now
            }
            result = self.conversations_collection.insert_one(conversation_document)
            return result.inserted_id
        except PyMongoError as e:
            logging.error(f"MongoDB error creating conversation for patient {patient_id}: {e}")
            return None

    def add_chat_message(self, message_data: Dict[str, Any]) -> Optional[ObjectId]:
        """
        Adds a new chat message to a conversation.

        Args:
            message_data: A dictionary containing the message details.
                          Expected keys: 'conversation_id', 'sender_type',
                                         'content', 'audio_url' (optional).

        Returns:
            The ObjectId of the newly created message, or None on error.
        """
        try:
            message_document = {
                "conversation_id": message_data.get("conversation_id"),
                "sender_type": message_data.get("sender_type"),
                "content": message_data.get("content"),
                "audio_url": message_data.get("audio_url"),
                "timestamp": datetime.now(timezone.utc)
            }
            result = self.messages_collection.insert_one(message_document)
            return result.inserted_id
        except PyMongoError as e:
            logging.error(f"MongoDB error adding chat message: {e}")
            return None

    def get_conversations_by_patient_id(self, patient_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all conversations for a specific patient.

        Args:
            patient_id: The ID of the patient.

        Returns:
            A list of conversation documents, sorted by start_time descending. Returns empty list on error.
        """
        try:
            conversations = self.conversations_collection.find(
                {"patient_id": patient_id}
            ).sort("start_time", -1)
            return [_serialize_document(convo) for convo in conversations]
        except PyMongoError as e:
            logging.error(f"MongoDB error getting conversations for patient {patient_id}: {e}")
            return []

    def get_messages_by_conversation_id(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all messages for a specific conversation.

        Args:
            conversation_id: The ID of the conversation.

        Returns:
            A list of message documents, sorted by timestamp ascending. Returns empty list on error.
        """
        try:
            conv_id = ObjectId(conversation_id)
        except Exception:
            return [] # Invalid ObjectId format

        try:
            messages = self.messages_collection.find(
                {"conversation_id": conv_id}
            ).sort("timestamp", 1)
            return [_serialize_document(msg) for msg in messages]
        except PyMongoError as e:
            logging.error(f"MongoDB error getting messages for conversation {conversation_id}: {e}")
            return []

    def find_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Finds a single conversation by its ID.

        Args:
            conversation_id: The ID of the conversation.

        Returns:
            The conversation document if found, otherwise None.
        """
        try:
            conv_id = ObjectId(conversation_id)
        except Exception:
            return None # Invalid ObjectId format

        try:
            return self.conversations_collection.find_one({"_id": conv_id})
        except PyMongoError as e:
            logging.error(f"MongoDB error finding conversation by id {conversation_id}: {e}")
            return None
