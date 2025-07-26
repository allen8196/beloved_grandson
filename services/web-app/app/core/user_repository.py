# services/web-app/app/core/user_repository.py
from ..models import User
from ..utils.extensions import db

class UserRepository:
    def find_by_account(self, account):
        """根據帳號尋找使用者"""
        return User.query.filter_by(account=account).first()

    def find_by_id(self, user_id):
        """根據 ID 尋找使用者"""
        return User.query.get(user_id)

    def find_by_email(self, email):
        """根據 Email 尋找使用者"""
        return User.query.filter_by(email=email).first()

    def find_by_line_user_id(self, line_user_id):
        """根據 LINE User ID 尋找使用者"""
        return User.query.filter_by(line_user_id=line_user_id).first()

    def add(self, user):
        """新增使用者到 session"""
        db.session.add(user)

    def commit(self):
        """提交 session 變更"""
        db.session.commit()
