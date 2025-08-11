# services/web-app/app/extensions.py
"""
This module initializes Flask extensions.
To avoid circular imports, extensions are initialized here
and then imported into the application factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flasgger import Swagger
from flask_socketio import SocketIO
from flask_apscheduler import APScheduler
from pymongo import MongoClient
import os

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
swagger = Swagger()
socketio = SocketIO()
scheduler = APScheduler()

# MongoDB Client
mongo_client = None

def init_mongo():
    """Initializes the MongoDB client."""
    global mongo_client
    mongo_uri = os.getenv("MONGO_URL")
    if not mongo_uri:
        raise ValueError("MONGO_URL environment variable is not set.")

    mongo_client = MongoClient(mongo_uri)

    try:
        mongo_client.admin.command('ping')
        print("MongoDB connection successful.")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")

def get_db():
    """Returns the MongoDB database instance."""
    if mongo_client is None:
        init_mongo()
    return mongo_client[os.getenv("MONGO_DB_NAME", "ai_assistant_db")]
