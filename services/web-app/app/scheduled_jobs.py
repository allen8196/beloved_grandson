"""
Top-level scheduled job wrappers that ensure a Flask app context.
Using string references (module:function) so jobs can be serialized by SQLAlchemyJobStore.

Avoid circular imports by importing create_app and job functions lazily inside the wrappers.
"""

import os


def _with_app_context(func_name: str):
    # Lazy import to avoid circular dependency during module import
    from app.app import create_app  # noqa: WPS433
    from app.core import scheduler_service  # noqa: WPS433

    func = getattr(scheduler_service, func_name)
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
