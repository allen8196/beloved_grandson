from flask import Flask
from flask_migrate import Migrate
from flasgger import Swagger

from app.config import Config
from app.models import db
from app.api import api_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Swagger Template
    template = {
        "swagger": "2.0",
        "info": {
            "title": "Beloved Grandson API",
            "description": "API for the Beloved Grandson application, handling user, conversation, and task management.",
            "version": "1.0.0"
        },
        "host": "localhost:5001",  # Adjust according to your Nginx setup
        "basePath": "/",  # The base path for all API endpoints
        "schemes": [
            "http",
            "https"
        ],
        "securityDefinitions": {
            "BearerAuth": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
            }
        }
    }

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)
    Swagger(app, template=template)

    # Register blueprints
    app.register_blueprint(api_bp)

    return app
