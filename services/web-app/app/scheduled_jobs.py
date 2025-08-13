"""
Top-level scheduled job wrappers that ensure a Flask app context.
Using string references (module:function) so jobs can be serialized by SQLAlchemyJobStore.

Avoid circular imports by importing create_app and job functions lazily inside the wrappers.
"""

import os


def _with_app_context(func_name: str):
    # 優先使用現有的 Flask app（避免重複初始化 scheduler）
    from app.core import scheduler_service  # noqa: WPS433
    func = getattr(scheduler_service, func_name)

    try:
        from flask import current_app  # noqa: WPS433
        app = current_app._get_current_object()
        with app.app_context():
            return func()
    except Exception:
        # 若目前執行緒沒有 app context，再以環境變數跳過 scheduler 初始化後建立 app
        import os
        os.environ["SKIP_SCHEDULER_INIT"] = "1"
        from app.app import create_app  # noqa: WPS433
        config_name = os.getenv("FLASK_CONFIG", "development")
        app, _ = create_app(config_name)
        with app.app_context():
            return func()


def run_noon_care_job():
    return _with_app_context("send_noon_care")


def run_survey_reminder_job():
    return _with_app_context("send_survey_reminder")


def run_evening_summary_job():
    return _with_app_context("send_evening_summary")
