# services/web-app/app/api/conversations.py

from flask import Blueprint, jsonify
from flasgger import swag_from

conversations_bp = Blueprint('conversations', __name__)

@conversations_bp.route('/', methods=['POST'])
@swag_from({
    'summary': '建立一個新的對話',
    'description': '開始一個新的對話 session。後續的實作將與 MongoDB 互動。',
    'tags': ['Conversations'],
    'responses': {
        '501': {
            'description': '功能尚未實作',
            'schema': {
                'properties': {
                    'message': {'type': 'string'},
                    'status': {'type': 'string'}
                }
            }
        }
    }
})
def create_conversation():
    """開始一個新的對話"""
    # 這裡的邏輯將會連接到 MongoDB 服務
    # from pymongo import MongoClient
    # client = MongoClient(current_app.config['MONGO_URI'])
    # db = client.get_default_database()
    # ...
    return jsonify({"message": "功能將在未來與 MongoDB 整合", "status": "Not Implemented"}), 501