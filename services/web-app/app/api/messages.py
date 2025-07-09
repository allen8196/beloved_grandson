from flask import Blueprint, request, jsonify
from app.utils.dependencies import container
from app.core.message_service import MessageService

messages_bp = Blueprint('messages_bp', __name__, url_prefix='/api/messages')

@messages_bp.route('', methods=['POST'])
def add_message():
    data = request.get_json()
    msg_service = container.resolve(MessageService)
    new_msg = msg_service.add_message(
        conversation_id=data['conversation_id'],
        role=data['role'],
        content=data['content']
    )
    return jsonify({'id': new_msg.id, 'role': new_msg.role, 'content': new_msg.content}), 201

@messages_bp.route('/<uuid:conversation_id>', methods=['GET'])
def get_messages(conversation_id):
    msg_service = container.resolve(MessageService)
    messages = msg_service.get_messages_by_conversation(conversation_id)
    return jsonify([{'id': m.id, 'role': m.role, 'content': m.content} for m in messages])
