# services/web-app/app/api/users.py

from flask import Blueprint, request, jsonify
from app.core import user_service
from flasgger import swag_from

users_bp = Blueprint('users', __name__)

@users_bp.route('/', methods=['POST'])
@swag_from({
    'summary': '建立新使用者',
    'description': '註冊一個新的使用者帳號。',
    'tags': ['Users'],
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'id': 'NewUser',
                'required': ['username', 'email', 'password'],
                'properties': {
                    'username': {
                        'type': 'string',
                        'description': '使用者名稱',
                        'example': 'john_doe'
                    },
                    'email': {
                        'type': 'string',
                        'description': '電子郵件地址',
                        'example': 'john.doe@example.com'
                    },
                    'password': {
                        'type': 'string',
                        'description': '使用者密碼',
                        'format': 'password',
                        'example': 'strong_password_123'
                    }
                }
            }
        }
    ],
    'responses': {
        '201': {
            'description': '使用者建立成功',
            'schema': {
                'properties': {
                    'message': {'type': 'string'},
                    'user': {
                        'properties': {
                            'id': {'type': 'integer'},
                            'username': {'type': 'string'},
                            'email': {'type': 'string'},
                            'created_at': {'type': 'string', 'format': 'date-time'}
                        }
                    }
                }
            }
        },
        '400': {
            'description': '請求無效或使用者已存在'
        }
    }
})
def create_user_endpoint():
    """建立新使用者"""
    data = request.get_json()
    user, message = user_service.create_user(data)
    if not user:
        return jsonify({"error": message}), 400
    return jsonify({"message": message, "user": user.to_dict()}), 201

@users_bp.route('/<int:user_id>', methods=['GET'])
@swag_from({
    'summary': '獲取使用者資訊',
    'description': '根據使用者 ID 獲取單一使���者的詳細資訊。',
    'tags': ['Users'],
    'parameters': [
        {
            'name': 'user_id',
            'in': 'path',
            'type': 'integer',
            'required': True,
            'description': '要查詢的使用者 ID'
        }
    ],
    'responses': {
        '200': {
            'description': '成功獲取使用者資訊',
            'schema': {
                'properties': {
                    'id': {'type': 'integer'},
                    'username': {'type': 'string'},
                    'email': {'type': 'string'},
                    'created_at': {'type': 'string', 'format': 'date-time'}
                }
            }
        },
        '404': {
            'description': '找不到指定的使用者'
        }
    }
})
def get_user_endpoint(user_id):
    """獲取使用者資訊"""
    user = user_service.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200
