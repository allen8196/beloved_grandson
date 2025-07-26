# services/web-app/tests/conftest.py
import pytest
from app.app import create_app
from app.utils.extensions import db as _db

@pytest.fixture(scope='session')
def app():
    """建立並設定一個新的 app 實例供測試使用"""
    app = create_app(config_name='testing')

    # 建立應用程式上下文
    with app.app_context():
        yield app

@pytest.fixture(scope='session')
def client(app):
    """為 app 建立一個測試客戶端"""
    return app.test_client()

@pytest.fixture(scope='function')
def db(app):
    """在每個測試函式執行前後，建立與清除資料庫"""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.close()
        _db.drop_all()

@pytest.fixture(scope='function')
def session(db):
    """回傳資料庫 session"""
    yield db.session
