# services/web-app/app/app.py

from flask import Flask, jsonify
from .config import config
from .utils.extensions import db, migrate, swagger, jwt, socketio
from .api.auth import auth_bp
from .api.patients import patients_bp
from .api.questionnaires import questionnaires_bp
from .api.uploads import uploads_bp
from .api.users import users_bp
from .api.daily_metrics import daily_metrics_bp

def create_app(config_name='default'):
    """
    應用程式工廠函數。
    """
    app = Flask(__name__)

    # 1. 載入設定
    app.config.from_object(config[config_name])

    # 2. 初始化擴充套件
    db.init_app(app)
    migrate.init_app(app, db)
    swagger.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app, async_mode='gevent', cors_allowed_origins="*")

    # Register Blueprints
    from .api.users import users_bp
    from .api.auth import auth_bp
    from .api.patients import patients_bp
    from .api.questionnaires import questionnaires_bp
    from .api.daily_metrics import daily_metrics_bp
    from .api.uploads import uploads_bp
    from .api.chat import bp as chat_bp # Explicitly import and alias the blueprint

    app.register_blueprint(users_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(questionnaires_bp)
    app.register_blueprint(daily_metrics_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(chat_bp) # Register the aliased blueprint

    # 4. 註冊全域錯誤處理器
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not Found", "message": "您請求的資源不存在。"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        # 在實際應用中，這裡應該記錄錯誤
        return jsonify({"error": "Internal Server Error", "message": "伺服器發生未預期的錯誤。"}), 500

    # 根路由，用於健康檢查
    @app.route('/')
    def index():
        return "Web App is running!"

    # WebSocket 事件處理
    @socketio.on('connect')
    def handle_connect():
        print('Client connected')

    @socketio.on('disconnect')
    def handle_disconnect():
        print('Client disconnected')

    return app, socketio
