# services/web-app/app/app.py
import os
from flask import Flask, jsonify
from .config import config
from .extensions import db, migrate, swagger, jwt, socketio, init_mongo, scheduler
from .api.auth import auth_bp
from .api.patients import patients_bp
from .api.questionnaires import questionnaires_bp
from .api.uploads import uploads_bp
from .api.users import users_bp
from .api.daily_metrics import daily_metrics_bp
from .api.chat import bp as chat_bp # Explicitly import and alias the blueprint
from .api.voice import bp as voice_bp # Import voice API blueprint
from .core.notification_service import start_notification_listener
from .core.scheduler_service import scheduled_task

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

    # 初始化排程器
    # We do this check to prevent the scheduler from starting during tests
    if config_name != 'testing':
        scheduler.init_app(app)
        scheduler.start()

    init_mongo()

    socketio.init_app(app, async_mode='gevent', cors_allowed_origins="*")

    app.register_blueprint(users_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(questionnaires_bp)
    app.register_blueprint(daily_metrics_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(chat_bp) # Register the aliased blueprint
    app.register_blueprint(voice_bp) # Register the voice API blueprint

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

    # Start the background notification listener
    # We do this check to prevent the listener from starting during tests
    if config_name != 'testing':
        start_notification_listener(app)

        # 在應用程式上下文中新增排程任務
        with app.app_context():
            # 確保只在主程序中新增任務，避免開發伺服器重載時重複新增
            # 在生產環境 (如 Gunicorn) 中，這個環境變數不存在，但 get_job() 會確保任務唯一性
            if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
                # 檢查任務是否已存在，若不存在才新增
                if not scheduler.get_job('scheduled_task_id'):
                    scheduler.add_job(
                        id='scheduled_task_id',
                        func=scheduled_task,
                        trigger='interval',
                        minutes=1,
                        replace_existing=True
                    )

    return app, socketio
