from flask import Blueprint, request, jsonify
from app.utils.dependencies import container
from app.core.user_service import UserService

users_bp = Blueprint('users_bp', __name__, url_prefix='/api/users')

@users_bp.route('', methods=['POST'])
def create_user():
    data = request.get_json()
    user_service = container.resolve(UserService)
    new_user = user_service.create_user(username=data['username'], email=data['email'])
    return jsonify({'id': new_user.id, 'username': new_user.username, 'email': new_user.email}), 201

@users_bp.route('/<uuid:user_id>', methods=['GET'])
def get_user(user_id):
    user_service = container.resolve(UserService)
    user = user_service.get_user_by_id(user_id)
    if user:
        return jsonify({'id': user.id, 'username': user.username, 'email': user.email})
    return jsonify({'error': 'User not found'}), 404
