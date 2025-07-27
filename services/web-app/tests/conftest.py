# services/web-app/tests/conftest.py
import pytest
from app.app import create_app
from app.extensions import db as _db, socketio as _socketio
from dotenv import load_dotenv
import os

# Load environment variables from .env file
# This is crucial for tests to access database URLs, etc.
# Make sure the .env file is in the root of the `services/web-app` directory
# or provide the correct path.
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    # If running tests from a different context, you might need to adjust
    # For docker-compose, the working dir is usually the project root
    load_dotenv()


@pytest.fixture(scope='session')
def app():
    """建立並設定一個新的 app 實例供測試使用"""
    # create_app 現在回傳 app 和 socketio
    app, socketio = create_app(config_name='testing')

    # 建立應用程式上下文
    with app.app_context():
        yield app, socketio

@pytest.fixture(scope='session')
def client(app):
    """為 app 建立一個測試客戶端"""
    # app fixture 現在是一個元組 (app, socketio)
    flask_app, _ = app
    return flask_app.test_client()

@pytest.fixture(scope='session')
def socketio_client(app):
    """為 app 建立一個 Socket.IO 測試客戶端"""
    flask_app, socketio = app
    return socketio.test_client(flask_app)

@pytest.fixture(scope='function')
def db(app):
    """在每個測試函式執行前後，建立與清除資料庫"""
    flask_app, _ = app
    with flask_app.app_context():
        _db.create_all()
        yield _db
        _db.session.close()
        _db.drop_all()

@pytest.fixture(scope='function')
def session(db):
    """回傳資料庫 session"""
    yield db.session
