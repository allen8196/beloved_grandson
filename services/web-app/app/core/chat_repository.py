# F:\iSpan_project\services\web-app\app\core\chat_repository.py
import logging
from app.extensions import get_db
from datetime import datetime, timezone
from bson import ObjectId
from typing import Dict, Any, Optional, List
from pymongo.errors import PyMongoError

def _serialize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    將 MongoDB 文件序列化，把 ObjectId 轉換成字串。
    """
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if "conversation_id" in doc and isinstance(doc["conversation_id"], ObjectId):
        doc["conversation_id"] = str(doc["conversation_id"])
    return doc

class ChatRepository:
    """
    處理 MongoDB 中聊天歷史資料的儲存庫 (Repository)。
    """
    def __init__(self):
        self.db = get_db()
        self.conversations_collection = self.db.conversations
        self.messages_collection = self.db.chat_messages

    def create_conversation(self, patient_id: int, therapist_id: Optional[int] = None) -> Optional[ObjectId]:
        """
        在資料庫中建立一個新的對話紀錄。

        參數 (Args):
            patient_id: 病患的 ID。
            therapist_id: 治療師的 ID (選填)。

        回傳 (Returns):
            新建立對話的 ObjectId，若發生錯誤則回傳 None。
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
            logging.error(f"為病患 {patient_id} 建立對話時發生 MongoDB 錯誤：{e}")
            return None

    def add_chat_message(self, message_data: Dict[str, Any]) -> Optional[ObjectId]:
        """
        為對話新增一則新的聊天訊息。

        參數 (Args):
            message_data: 包含訊息細節的字典。
                          預期包含的鍵 (keys) 為：'conversation_id'、'sender_type'、
                          'content'、'audio_url' (選填)。

        回傳 (Returns):
            新建立訊息的 ObjectId，若發生錯誤則回傳 None。
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
            logging.error(f"新增聊天訊息時發生 MongoDB 錯誤：{e}")
            return None

    def get_conversations_by_patient_id(self, patient_id: int) -> List[Dict[str, Any]]:
        """
        擷取某個特定病患的所有對話。

        參數 (Args):
            patient_id: 病患的 ID。

        回傳 (Returns):
            一個對話文件 (documents) 的列表，依據 start_time 降冪排序。若發生錯誤則回傳空列表。
        """
        try:
            conversations = self.conversations_collection.find(
                {"patient_id": patient_id}
            ).sort("start_time", -1)
            return [_serialize_document(convo) for convo in conversations]
        except PyMongoError as e:
            logging.error(f"為病患 {patient_id} 取得對話時發生 MongoDB 錯誤：{e}")
            return []

    def get_messages_by_conversation_id(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        擷取某個特定對話的所有訊息。

        參數 (Args):
            conversation_id: 對話的 ID。

        回傳 (Returns):
            一個訊息文件 (documents) 的列表，依據 timestamp 升冪排序。若發生錯誤則回傳空列表。
        """
        try:
            conv_id = ObjectId(conversation_id)
        except Exception:
            return [] # 無效的 ObjectId 格式

        try:
            messages = self.messages_collection.find(
                {"conversation_id": conv_id}
            ).sort("timestamp", 1)
            return [_serialize_document(msg) for msg in messages]
        except PyMongoError as e:
            logging.error(f"為對話 {conversation_id} 取得訊息時發生 MongoDB 錯誤：{e}")
            return []

    def find_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        透過 ID 尋找單一對話。

        參數 (Args):
            conversation_id: 對話的 ID。

        回傳 (Returns):
            如果找到對話文件 (document) 則回傳該文件，否則回傳 None。
        """
        try:
            conv_id = ObjectId(conversation_id)
        except Exception:
            return None # 無效的 ObjectId 格式

        try:
            return self.conversations_collection.find_one({"_id": conv_id})
        except PyMongoError as e:
            logging.error(f"透過 ID {conversation_id} 尋找對話時發生 MongoDB 錯誤：{e}")
            return None
