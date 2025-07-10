# services/web-app/app/core/user_service.py

from app.utils.extensions import db
from app.models.user import User
# 在實際應用中，這裡會加入密碼雜湊的邏輯
from werkzeug.security import generate_password_hash, check_password_hash

def create_user(data):
    """建立新使用者"""
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return None, "缺少必要欄位 (username, email, password)"

    if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
        return None, "使用者名稱或電子郵件已存在"

    password_hash = generate_password_hash(password) # 實際應儲存雜湊後的密碼
    new_user = User(username=username, email=email, password_hash=password_hash)

    db.session.add(new_user)
    db.session.commit()

    return new_user, "使用者建立成功"

def get_user_by_id(user_id):
    """透過 ID 尋找使用者"""
    return User.query.get(user_id)
