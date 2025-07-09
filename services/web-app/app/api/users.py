# services/web-app/app/api/users.py

from flask import Blueprint, request, jsonify
from flasgger import swag_from
# from app.utils.dependencies import container
# from app.core.user_service import UserService

# Using the original blueprint name and prefix for consistency
users_bp = Blueprint('users_bp', __name__, url_prefix='/api/users')

# --- Swagger Definitions ---
USER_DEFINITIONS = {
    "definitions": {
        "User": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "format": "uuid", "description": "User's unique ID."},
                "full_name": {"type": "string", "description": "User's full name."},
                "email": {"type": "string", "format": "email", "description": "User's email address."},
                "created_at": {"type": "string", "format": "date-time", "description": "Timestamp of user creation."}
            }
        },
        "UserInput": {
            "type": "object",
            "required": ["email", "password", "full_name"],
            "properties": {
                "full_name": {"type": "string", "example": "John Doe"},
                "email": {"type": "string", "format": "email", "example": "john.doe@example.com"},
                "password": {"type": "string", "format": "password", "example": "a_strong_password"}
            }
        },
        "LoginCredentials": {
            "type": "object",
            "required": ["email", "password"],
            "properties": {
                "email": {"type": "string", "format": "email"},
                "password": {"type": "string", "format": "password"}
            }
        },
        "TokenResponse": {
            "type": "object",
            "properties": {
                "access_token": {"type": "string", "description": "JWT access token."}
            }
        },
        "ErrorResponse": {
            "type": "object",
            "properties": {
                "error": {"type": "string", "description": "A description of the error."}
            }
        }
    }
}

@users_bp.route('/register', methods=['POST'])
@swag_from({
    **USER_DEFINITIONS,
    'tags': ['User Management'],
    'summary': 'Register a new user',
    'parameters': [
        {
            'in': 'body',
            'name': 'body',
            'schema': {'$ref': '#/definitions/UserInput'},
            'required': True,
            'description': 'User registration details.'
        }
    ],
    'responses': {
        '201': {
            'description': 'User created successfully.',
            'schema': {'$ref': '#/definitions/User'}
        },
        '400': {
            'description': 'Invalid input or user already exists.',
            'schema': {'$ref': '#/definitions/ErrorResponse'}
        }
    }
})
def register():
    """處理新使用者註冊。"""
    data = request.get_json()
    # user_service = container.resolve(UserService)
    # new_user = user_service.create_user(email=data['email'], password=data['password'], full_name=data['full_name'])
    # This is a mock response for demonstration
    new_user = {
        "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "email": data['email'],
        "full_name": data['full_name'],
        "created_at": "2023-10-27T10:00:00Z"
    }
    return jsonify(new_user), 201

@users_bp.route('/login', methods=['POST'])
@swag_from({
    'tags': ['User Management'],
    'summary': 'Log in a user',
    'parameters': [
        {
            'in': 'body',
            'name': 'body',
            'schema': {'$ref': '#/definitions/LoginCredentials'},
            'required': True,
            'description': 'User login credentials.'
        }
    ],
    'responses': {
        '200': {
            'description': 'Login successful, returns access token.',
            'schema': {'$ref': '#/definitions/TokenResponse'}
        },
        '401': {
            'description': 'Invalid credentials.',
            'schema': {'$ref': '#/definitions/ErrorResponse'}
        }
    }
})
def login():
    """處理使用者登入及權杖生成。"""
    # ... Add actual login logic here ...
    return jsonify({"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}), 200

@users_bp.route('/me', methods=['GET'])
@swag_from({
    'tags': ['User Management'],
    'summary': 'Get current user profile',
    'security': [{'BearerAuth': []}],
    'responses': {
        '200': {
            'description': 'Successfully retrieved user profile.',
            'schema': {'$ref': '#/definitions/User'}
        },
        '401': {
            'description': 'Unauthorized or invalid token.',
            'schema': {'$ref': '#/definitions/ErrorResponse'}
        }
    }
})
def get_me():
    """擷取目前已驗證使用者的個人資料。"""
    # ... Add actual logic to get user from JWT here ...
    user_data = {
        "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
        "email": "user@example.com",
        "full_name": "Current User",
        "created_at": "2023-10-27T10:00:00Z"
    }
    return jsonify(user_data), 200
