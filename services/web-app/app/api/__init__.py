from flask import Blueprint

from .users import users_bp
from .conversations import conversations_bp
from .messages import messages_bp

api_bp = Blueprint('api', __name__)

api_bp.register_blueprint(users_bp)
api_bp.register_blueprint(conversations_bp)
api_bp.register_blueprint(messages_bp)
