# services/web-app/tests/test_auth.py
import json
import pytest
from app.models.models import User, StaffDetail

def test_register_success(client, session):
    """
    測試案例: 使用有效資料成功註冊
    """
    # Arrange
    data = {
        "lineUserId": "U_test_register_success",
        "first_name": "測試",
        "last_name": "成功",
        "gender": "other",
        "phone": "0987654321",
        "height_cm": 170,
        "weight_kg": 65,
        "smoke_status": "never"
    }

    # Act
    response = client.post('/api/v1/auth/line/register', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 201
    json_data = response.get_json()
    assert 'token' in json_data['data']
    assert json_data['data']['user']['line_user_id'] == "U_test_register_success"

    # Verify database
    user = User.query.filter_by(line_user_id="U_test_register_success").first()
    assert user is not None
    assert user.health_profile.height_cm == 170

def test_register_conflict(client, session):
    """
    測試案例: 使用已存在的 lineUserId 註冊
    """
    # Arrange: First, create a user
    existing_user = User(line_user_id="U_test_conflict", account="conflict_user")
    existing_user.set_password("anypassword")
    session.add(existing_user)
    session.commit()

    data = {
        "lineUserId": "U_test_conflict",
        "first_name": "測試",
        "last_name": "衝突"
    }

    # Act
    response = client.post('/api/v1/auth/line/register', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 409
    json_data = response.get_json()
    assert json_data['error']['code'] == 'USER_ALREADY_EXISTS'

def test_register_missing_fields(client, session):
    """
    測試案例: 缺少必要欄位
    """
    # Arrange
    data = {
        "lineUserId": "U_test_missing_fields"
        # Missing first_name and last_name
    }

    # Act
    response = client.post('/api/v1/auth/line/register', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error']['code'] == 'INVALID_INPUT'

# --- Therapist Login Tests ---

@pytest.fixture(scope="function")
def therapist(session):
    """建立一個治療師用於登入測試"""
    user = User(
        account='therapist_test_user',
        first_name='治療師',
        last_name='測試員',
        is_staff=True
    )
    user.set_password('good_password')
    user.staff_details = StaffDetail(title='呼吸治療師')
    session.add(user)
    session.commit()
    return user

def test_therapist_login_success(client, therapist):
    """
    測試案例: 治療師使用正確的帳號密碼成功登入
    """
    # Arrange
    data = {
        "account": "therapist_test_user",
        "password": "good_password"
    }

    # Act
    response = client.post('/api/v1/auth/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'token' in json_data['data']
    assert json_data['data']['user']['account'] == 'therapist_test_user'

def test_therapist_login_wrong_password(client, therapist):
    """
    測試案例: 治療師使用錯誤的密碼登入
    """
    # Arrange
    data = {
        "account": "therapist_test_user",
        "password": "wrong_password"
    }

    # Act
    response = client.post('/api/v1/auth/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data['error']['code'] == 'INVALID_CREDENTIALS'

def test_therapist_login_nonexistent_user(client, db):
    """
    測試案例: 治療師使用不存在的帳號登入
    """
    # Arrange
    data = {
        "account": "nonexistent_user",
        "password": "any_password"
    }

    # Act
    response = client.post('/api/v1/auth/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data['error']['code'] == 'INVALID_CREDENTIALS'

# --- Admin User Creation Tests ---

@pytest.fixture(scope="function")
def admin_token(client, session):
    """建立一個管理員並回傳其 JWT token"""
    admin = User(account='admin_for_test', is_staff=True, is_admin=True)
    admin.set_password('admin_password')
    session.add(admin)
    session.commit()

    login_data = {"account": "admin_for_test", "password": "admin_password"}
    response = client.post('/api/v1/auth/login', data=json.dumps(login_data), content_type='application/json')
    return response.get_json()['data']['token']

def test_admin_create_user_success(client, admin_token):
    """
    測試案例: 管理員成功建立一個新的治療師
    """
    # Arrange
    headers = {'Authorization': f'Bearer {admin_token}'}
    new_user_data = {
        "account": "new_therapist_by_admin",
        "password": "a_strong_password",
        "first_name": "新治療師",
        "last_name": "管",
        "is_staff": True,
        "is_admin": False,
        "title": "呼吸治療師"
    }

    # Act
    response = client.post('/api/v1/users/', data=json.dumps(new_user_data), headers=headers, content_type='application/json')

    # Assert
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data['data']['account'] == 'new_therapist_by_admin'

    # Verify database
    user = User.query.filter_by(account='new_therapist_by_admin').first()
    assert user is not None
    assert user.is_staff is True

def test_admin_create_user_unauthorized(client, therapist):
    """
    測試案例: 非管理員 (普通治療師) 嘗試建立使用者
    """
    # Arrange: Login as a normal therapist to get a token
    login_data = {"account": therapist.account, "password": "good_password"}
    login_response = client.post('/api/v1/auth/login', data=json.dumps(login_data), content_type='application/json')
    therapist_token = login_response.get_json()['data']['token']

    headers = {'Authorization': f'Bearer {therapist_token}'}
    new_user_data = {"account": "another_user", "password": "pw"}

    # Act
    response = client.post('/api/v1/users/', data=json.dumps(new_user_data), headers=headers, content_type='application/json')

    # Assert
    assert response.status_code == 403

def test_admin_create_user_conflict(client, admin_token):
    """
    測試案例: 管理員嘗試建立一個已存在的帳號
    """
    # Arrange
    headers = {'Authorization': f'Bearer {admin_token}'}
    user_data = {
        "account": "existing_user_for_conflict",
        "password": "pw",
        "first_name": "已存在", "last_name": "員"
    }
    # Create the user first
    client.post('/api/v1/users/', data=json.dumps(user_data), headers=headers, content_type='application/json')

    # Act: Try to create it again
    response = client.post('/api/v1/users/', data=json.dumps(user_data), headers=headers, content_type='application/json')

    # Assert
    assert response.status_code == 409


# --- Line Login Tests ---

@pytest.fixture(scope="function")
def line_user(session):
    """建立一個已註冊的 LINE 使用者"""
    user = User(
        line_user_id='U_registered_line_user',
        account='line_user_account',
        first_name='LINE',
        last_name='使用者'
    )
    user.set_password('any_password')
    session.add(user)
    session.commit()
    return user

def test_line_login_success(client, line_user):
    """
    測試案例: 已註冊的 LINE 使用者成功登入
    """
    # Arrange
    data = {"lineUserId": "U_registered_line_user"}

    # Act
    response = client.post('/api/v1/auth/line/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'token' in json_data['data']
    assert json_data['data']['user']['line_user_id'] == 'U_registered_line_user'

def test_line_login_not_found(client, db):
    """
    測試案例: 未註冊的 LINE 使用者嘗試登入
    """
    # Arrange
    data = {"lineUserId": "U_unregistered_line_user"}

    # Act
    response = client.post('/api/v1/auth/line/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data['error']['code'] == 'USER_NOT_FOUND'

def test_line_login_missing_id(client, db):
    """
    測試案例: LINE 登入請求缺少 lineUserId
    """
    # Arrange
    data = {"another_field": "some_value"}

    # Act
    response = client.post('/api/v1/auth/line/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error']['code'] == 'INVALID_INPUT'

# --- Error Handling and Edge Case Tests ---

def test_login_invalid_json(client):
    """
    測試案例: 登入請求的 body 不是有效的 JSON
    """
    # Arrange
    data = "this is not json"

    # Act
    response = client.post('/api/v1/auth/login', data=data, content_type='application/json')

    # Assert
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error']['code'] == 'BAD_REQUEST'

def test_login_missing_credentials(client):
    """
    測試案例: 登入請求缺少帳號或密碼
    """
    # Arrange
    data = {"account": "some_user"} # Missing password

    # Act
    response = client.post('/api/v1/auth/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error']['code'] == 'INVALID_INPUT'

def test_login_service_exception(client, monkeypatch, therapist):
    """
    測試案例: 登入過程中，核心服務層拋出未預期的例外
    """
    # Arrange
    def mock_login_user(account, password):
        raise Exception("Database connection failed")
    
    monkeypatch.setattr('app.api.auth.login_user', mock_login_user)
    
    data = {"account": "any_user", "password": "any_password"}

    # Act
    response = client.post('/api/v1/auth/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 500
    json_data = response.get_json()
    assert json_data['error']['code'] == 'INTERNAL_SERVER_ERROR'

def test_login_jwt_creation_exception(client, monkeypatch, therapist):
    """
    測試案例: 成功驗證使用者後，生成 JWT 時發生例外
    """
    # Arrange
    def mock_create_token(identity, expires_delta):
        raise Exception("JWT secret key is misconfigured")

    monkeypatch.setattr('app.api.auth.create_access_token', mock_create_token)

    data = {"account": therapist.account, "password": "good_password"}

    # Act
    response = client.post('/api/v1/auth/login', data=json.dumps(data), content_type='application/json')

    # Assert
    assert response.status_code == 500
    json_data = response.get_json()
    assert json_data['error']['code'] == 'INTERNAL_SERVER_ERROR'
