# services/web-app/app/api/auth.py
from flask import Blueprint, request, jsonify
from flasgger import swag_from
from flask_jwt_extended import create_access_token
from ..core.auth_service import login_user, login_line_user, register_line_user
from datetime import timedelta

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/login', methods=['POST'])
@swag_from({
    'summary': '呼吸治療師登入',
    'description': '供呼吸治療師使用帳號密碼進行登入。',
    'tags': ['Authentication'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'id': 'Login',
                'required': ['account', 'password'],
                'properties': {
                    'account': {'type': 'string', 'example': 'admin'},
                    'password': {'type': 'string', 'format': 'password', 'example': 'admin'}
                }
            }
        }
    ],
    'responses': {
        '200': {'description': '登入成功'},
        '401': {'description': '帳號或密碼錯誤'}
    }
})
def handle_login():
    """處理使用者登入"""
    data = request.get_json()
    account = data.get('account')
    password = data.get('password')

    user = login_user(account, password)

    if not user:
        return jsonify({"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid account or password."}}), 401

    identity = str(user.id)
    expires = timedelta(hours=1)
    access_token = create_access_token(identity=identity, expires_delta=expires)

    user_info = {
        "id": user.id,
        "account": user.account,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
    if user.is_staff and hasattr(user, 'staff_details') and user.staff_details:
        user_info['title'] = user.staff_details.title

    return jsonify({
        "data": {
            "token": access_token,
            "expires_in": expires.total_seconds(),
            "user": user_info
        }
    }), 200

@auth_bp.route('/line/login', methods=['POST'])
@swag_from({
    'summary': '患者 LIFF 登入',
    'description': '供**已註冊**的患者在 LIFF 環境中，使用 `lineUserId` 進行登入。',
    'tags': ['Authentication'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'id': 'LineLogin',
                'required': ['lineUserId'],
                'properties': {
                    'lineUserId': {'type': 'string', 'example': 'U123456789abcdef123456789abcdef'}
                }
            }
        }
    ],
    'responses': {
        '200': {'description': '登入成功'},
        '400': {'description': 'lineUserId 缺失'},
        '404': {'description': '使用者未註冊'}
    }
})
def handle_line_login():
    """處理 LINE 使用者登入"""
    data = request.get_json()
    line_user_id = data.get('lineUserId')

    if not line_user_id:
        return jsonify({"error": {"code": "INVALID_INPUT", "message": "lineUserId is required."}}), 400

    user = login_line_user(line_user_id)

    if not user:
        return jsonify({"error": {"code": "USER_NOT_FOUND", "message": "This LINE account is not registered."}}), 404

    identity = str(user.id)
    expires = timedelta(days=7)
    access_token = create_access_token(identity=identity, expires_delta=expires)

    user_info = {
        "id": user.id,
        "line_user_id": user.line_user_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "health_profile": {
            "height_cm": user.health_profile.height_cm if user.health_profile else None,
            "weight_kg": user.health_profile.weight_kg if user.health_profile else None,
            "smoke_status": user.health_profile.smoke_status if user.health_profile else None,
        }
    }

    return jsonify({
        "data": {
            "token": access_token,
            "expires_in": expires.total_seconds(),
            "user": user_info
        }
    }), 200

@auth_bp.route('/line/register', methods=['POST'])
@swag_from({
    'summary': '患者 LIFF 註冊',
    'description': '供新患者在 LIFF 環境中，使用 `lineUserId` 並填寫基本資料以完成註冊。',
    'tags': ['Authentication'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'id': 'LineRegister',
                'required': ['lineUserId', 'first_name', 'last_name'],
                'properties': {
                    'lineUserId': {'type': 'string', 'example': 'U_new_user_abcdef123456'},
                    'first_name': {'type': 'string', 'example': '美麗'},
                    'last_name': {'type': 'string', 'example': '陳'},
                    'gender': {'type': 'string', 'example': 'female'},
                    'phone': {'type': 'string', 'example': '0987654321'},
                    'height_cm': {'type': 'integer', 'example': 160},
                    'weight_kg': {'type': 'integer', 'example': 55},
                    'smoke_status': {'type': 'string', 'example': 'never'}
                }
            }
        }
    ],
    'responses': {
        '201': {'description': '註冊成功並自動登入'},
        '400': {'description': '缺少必要欄位'},
        '409': {'description': '使用者已存在'}
    }
})
def handle_line_register():
    """處理 LINE 使用者註冊"""
    data = request.get_json()
    
    new_user, error_msg = register_line_user(data)

    if error_msg:
        status_code = 409 if "already registered" in error_msg else 400
        error_code = "USER_ALREADY_EXISTS" if status_code == 409 else "INVALID_INPUT"
        return jsonify({"error": {"code": error_code, "message": error_msg}}), status_code

    identity = str(new_user.id)
    expires = timedelta(days=7)
    access_token = create_access_token(identity=identity, expires_delta=expires)

    user_info = {
        "id": new_user.id,
        "line_user_id": new_user.line_user_id,
        "first_name": new_user.first_name,
        "last_name": new_user.last_name
    }

    return jsonify({
        "data": {
            "token": access_token,
            "expires_in": expires.total_seconds(),
            "user": user_info
        }
    }), 201
