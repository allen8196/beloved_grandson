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
from .api.chat import bp as chat_bp  # Explicitly import and alias the blueprint
from .api.voice import bp as voice_bp  # Import voice API blueprint
from .core.notification_service import start_notification_listener

# 從原本示範任務，改為引入實際排程任務（保留原檔案中的示範函式，不再註冊）
from .core.scheduler_service import scheduled_task
from .scheduled_jobs import (
    run_noon_care_job,
    run_survey_reminder_job,
    run_evening_summary_job,
)


def create_app(config_name="default"):
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

    # 初始化排程器（允許在排程執行緒或子流程中跳過，以避免重複啟動）
    # 以環境變數 SKIP_SCHEDULER_INIT=1 控制略過
    if config_name != "testing" and os.getenv("SKIP_SCHEDULER_INIT") != "1":
        scheduler.init_app(app)
        scheduler.start()

    init_mongo()

    socketio.init_app(app, async_mode="gevent", cors_allowed_origins="*")

    app.register_blueprint(users_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(questionnaires_bp)
    app.register_blueprint(daily_metrics_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(chat_bp)  # Register the aliased blueprint
    app.register_blueprint(voice_bp)  # Register the voice API blueprint

    # 4. 註冊全域錯誤處理器
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not Found", "message": "您請求的資源不存在。"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        # 在實際應用中，這裡應該記錄錯誤
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "伺服器發生未預期的錯誤。",
                }
            ),
            500,
        )

    # 根路由，用於健康檢查
    @app.route("/")
    def index():
        return "Web App is running!"

    # WebSocket 事件處理
    @socketio.on("connect")
    def handle_connect():
        print("Client connected")

    @socketio.on("disconnect")
    def handle_disconnect():
        print("Client disconnected")

    # Start the background notification listener
    # We do this check to prevent the listener from starting during tests
    if config_name != "testing":
        start_notification_listener(app)

        # 在應用程式上下文中新增排程任務
        with app.app_context():
            # 確保只在主程序中新增/調整任務，避免開發伺服器重載時重複新增
            # 在生產環境 (如 Gunicorn) 中，這個環境變數不存在，但 get_job() / reschedule_job() 會確保唯一性
            if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
                # 允許以環境變數覆寫時間，便於臨時測試
                def get_time(env_h: str, env_m: str, default_h: int, default_m: int):
                    try:
                        h = int(os.getenv(env_h, default_h))
                        m = int(os.getenv(env_m, default_m))
                        return h, m
                    except Exception:
                        return default_h, default_m

                # 確保任務在 app_context 中執行，避免 current_app 取值錯誤
                def make_context_job(f):
                    def _job():
                        with app.app_context():
                            return f()

                    return _job

                def add_or_reschedule(
                    job_id: str, func_path: str, hour: int, minute: int
                ):
                    job = scheduler.get_job(job_id)
                    # 以文字引用可被 SQLAlchemy JobStore 序列化
                    if job:
                        scheduler.remove_job(job_id)
                    scheduler.add_job(
                        id=job_id,
                        func=func_path,
                        trigger="cron",
                        hour=hour,
                        minute=minute,
                        replace_existing=True,
                        misfire_grace_time=60,
                        max_instances=1,
                        coalesce=True,
                    )

                # 讀取三個任務時間（預設：12:30、17:30、20:00 台北時區）
                noon_h, noon_m = get_time("NOON_CARE_HOUR", "NOON_CARE_MINUTE", 12, 30)
                survey_h, survey_m = get_time(
                    "SURVEY_REMINDER_HOUR", "SURVEY_REMINDER_MINUTE", 17, 30
                )
                evening_h, evening_m = get_time(
                    "EVENING_SUMMARY_HOUR", "EVENING_SUMMARY_MINUTE", 20, 00
                )


                # 設定或重排程
                add_or_reschedule(
                    "noon_care", "app.scheduled_jobs:run_noon_care_job", noon_h, noon_m
                )
                add_or_reschedule(
                    "survey_reminder",
                    "app.scheduled_jobs:run_survey_reminder_job",
                    survey_h,
                    survey_m,
                )
                add_or_reschedule(
                    "evening_summary",
                    "app.scheduled_jobs:run_evening_summary_job",
                    evening_h,
                    evening_m,
                )
                # 注意：原本的每分鐘示範任務不再註冊，避免與實際任務混淆

    return app, socketio
