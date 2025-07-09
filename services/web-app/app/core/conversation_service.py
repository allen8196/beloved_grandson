from sqlalchemy.orm import Session
from app.models import Conversation
from typing import List

class ConversationService:
    def __init__(self, session: Session):
        self.session = session

    def create_conversation(self, user_id: str, title: str) -> Conversation:
        new_conversation = Conversation(user_id=user_id, title=title)
        self.session.add(new_conversation)
        self.session.commit()
        return new_conversation

    def get_conversations_by_user(self, user_id: str) -> List[Conversation]:
        return self.session.query(Conversation).filter_by(user_id=user_id).all()

    def get_conversation_by_id(self, conversation_id: str) -> Conversation:
        return self.session.query(Conversation).filter_by(id=conversation_id).first()

    def delete_conversation(self, conversation_id: str) -> bool:
        conversation = self.get_conversation_by_id(conversation_id)
        if conversation:
            self.session.delete(conversation)
            self.session.commit()
            return True
        return False
