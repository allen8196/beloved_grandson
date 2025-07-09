from sqlalchemy.orm import Session
from app.models import User

class UserService:
    def __init__(self, session: Session):
        self.session = session

    def create_user(self, username: str, email: str) -> User:
        new_user = User(username=username, email=email)
        self.session.add(new_user)
        self.session.commit()
        return new_user

    def get_user_by_id(self, user_id: str) -> User:
        return self.session.query(User).filter_by(id=user_id).first()
