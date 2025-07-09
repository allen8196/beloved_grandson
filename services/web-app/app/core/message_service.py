from sqlalchemy.orm import Session
from app.models import Message
from typing import List

class MessageService:
    def __init__(self, session: Session):
        self.session = session

    def add_message(self, conversation_id: str, role: str, content: str) -> Message:
        new_message = Message(conversation_id=conversation_id, role=role, content=content)
        self.session.add(new_message)
        self.session.commit()
        return new_message

    def get_messages_by_conversation(self, conversation_id: str) -> List[Message]:
        return self.session.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.created_at.asc()).all()
