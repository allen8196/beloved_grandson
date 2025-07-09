# services/web-app/app/api/conversations.py

from flask import Blueprint, request, jsonify
from flasgger import swag_from

# 為了演示，暫時註解依賴注入
# from app.utils.dependencies import container
# from app.core.conversation_service import ConversationService

conversations_bp = Blueprint('conversations_bp', __name__, url_prefix='/api/conversations')

# --- Swagger Definitions ---
CONVERSATION_DEFINITIONS = {
    "definitions": {
        "TaskCreationResponse": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "format": "uuid", "description": "The unique ID for the asynchronous processing task."}
            }
        },
        "ConversationSummary": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "user_id": {"type": "string", "format": "uuid"},
                "title": {"type": "string", "description": "Title of the conversation."},
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"}
            }
        },
        "Message": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "sender_type": {"type": "string", "enum": ["USER", "AI"]},
                "text_content": {"type": "string"},
                "audio_input_url": {"type": "string", "format": "uri", "nullable": True},
                "audio_output_url": {"type": "string", "format": "uri", "nullable": True},
                "created_at": {"type": "string", "format": "date-time"}
            }
        },
        "ConversationDetail": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "title": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
                "messages": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/Message"}
                }
            }
        }
    }
}

@conversations_bp.route('', methods=['POST'])
@swag_from({
    **CONVERSATION_DEFINITIONS,
    'tags': ['Conversation & Task Management'],
    'summary': 'Submit a new conversation task with an audio file.',
    'consumes': ['multipart/form-data'],
    'security': [{'BearerAuth': []}],
    'parameters': [
        {
            'name': 'audio_file',
            'in': 'formData',
            'type': 'file',
            'required': True,
            'description': 'The user\'s input audio file (e.g., .wav, .mp3).'
        },
        {
            'name': 'conversation_id',
            'in': 'formData',
            'type': 'string',
            'format': 'uuid',
            'required': False,
            'description': 'Optional ID of an existing conversation to add the message to.'
        }
    ],
    'responses': {
        '202': {
            'description': 'Task accepted for processing.',
            'schema': {'$ref': '#/definitions/TaskCreationResponse'}
        },
        '401': {'description': 'Unauthorized.'}
    }
})
def submit_conversation_task():
    """Accepts an audio file to start or continue a conversation."""
    # conv_service = container.resolve(ConversationService)
    # task_id = conv_service.submit_task(request.files['audio_file'], request.form.get('conversation_id'))
    # Mock response:
    task_id = "f1g2h3i4-j5k6-7890-1234-567890lmnpqr"
    return jsonify({"task_id": task_id}), 202

@conversations_bp.route('', methods=['GET'])
@swag_from({
    'tags': ['Conversation History'],
    'summary': 'List all conversations for the current user.',
    'security': [{'BearerAuth': []}],
    'responses': {
        '200': {
            'description': 'A list of conversation summaries.',
            'schema': {
                'type': 'array',
                'items': {'$ref': '#/definitions/ConversationSummary'}
            }
        },
        '401': {'description': 'Unauthorized.'}
    }
})
def list_conversations():
    """Retrieves a list of all conversations for the authenticated user."""
    # Mock response:
    conversations = [
        {
            "id": "c1d2e3f4-g5h6-7890-1234-567890ijklmn",
            "user_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
            "title": "關於天氣的對話",
            "created_at": "2023-10-27T10:05:00Z",
            "updated_at": "2023-10-27T10:15:00Z"
        }
    ]
    return jsonify(conversations)

@conversations_bp.route('/<uuid:conversation_id>', methods=['GET'])
@swag_from({
    'tags': ['Conversation History'],
    'summary': 'Get the full content of a specific conversation.',
    'security': [{'BearerAuth': []}],
    'parameters': [
        {
            'name': 'conversation_id',
            'in': 'path',
            'type': 'string',
            'format': 'uuid',
            'required': True
        }
    ],
    'responses': {
        '200': {
            'description': 'The detailed conversation including all messages.',
            'schema': {'$ref': '#/definitions/ConversationDetail'}
        },
        '401': {'description': 'Unauthorized.'},
        '404': {'description': 'Conversation not found.'}
    }
})
def get_conversation_detail(conversation_id):
    """Retrieves a single conversation and all its messages."""
    # Mock response:
    conversation_detail = {
        "id": str(conversation_id),
        "title": "關於天氣的對話",
        "created_at": "2023-10-27T10:05:00Z",
        "messages": [
            {
                "id": "m1n2o3p4-q5r6-7890-1234-567890stuvwx",
                "sender_type": "USER",
                "text_content": "今天天氣如何？",
                "audio_input_url": "/media/audio-inputs/abc.wav",
                "created_at": "2023-10-27T10:05:10Z"
            },
            {
                "id": "x1y2z3a4-b5c6-7890-1234-567890defghi",
                "sender_type": "AI",
                "text_content": "天氣晴朗，氣溫攝氏25度。",
                "audio_output_url": "/media/audio-outputs/xyz.mp3",
                "created_at": "2023-10-27T10:05:15Z"
            }
        ]
    }
    return jsonify(conversation_detail)