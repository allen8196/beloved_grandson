from flask import Flask
from flask_migrate import Migrate

from app.config import Config
from app.models import db
from app.api import api_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)

    # Register blueprints
    app.register_blueprint(api_bp)

    return app
