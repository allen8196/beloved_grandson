import punq

from app.core.user_service import UserService
from app.core.conversation_service import ConversationService
from app.core.message_service import MessageService
from app.models import db

def get_container() -> punq.Container:
    container = punq.Container()

    # Register Services
    container.register(UserService, factory=lambda: UserService(db.session))
    container.register(ConversationService, factory=lambda: ConversationService(db.session))
    container.register(MessageService, factory=lambda: MessageService(db.session))

    return container

# Global container
container = get_container()
