from flask import Blueprint, request, jsonify
from app.utils.dependencies import container
from app.core.conversation_service import ConversationService

conversations_bp = Blueprint('conversations_bp', __name__, url_prefix='/api/conversations')

@conversations_bp.route('', methods=['POST'])
def create_conversation():
    data = request.get_json()
    conv_service = container.resolve(ConversationService)
    new_conv = conv_service.create_conversation(user_id=data['user_id'], title=data['title'])
    return jsonify({'id': new_conv.id, 'title': new_conv.title}), 201

@conversations_bp.route('', methods=['GET'])
def get_conversations():
    user_id = request.args.get('user_id')
    conv_service = container.resolve(ConversationService)
    convs = conv_service.get_conversations_by_user(user_id)
    return jsonify([{'id': c.id, 'title': c.title, 'user_id': c.user_id} for c in convs])

@conversations_bp.route('/<uuid:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    conv_service = container.resolve(ConversationService)
    conv = conv_service.get_conversation_by_id(conversation_id)
    if conv:
        return jsonify({'id': conv.id, 'title': conv.title, 'user_id': conv.user_id})
    return jsonify({'error': 'Conversation not found'}), 404

@conversations_bp.route('/<uuid:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    conv_service = container.resolve(ConversationService)
    if conv_service.delete_conversation(conversation_id):
        return '', 204
    return jsonify({'error': 'Conversation not found'}), 404
