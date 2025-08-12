from app.app import create_app
from app.extensions import db
from app.core.scheduler_service import (
    send_noon_care,
    send_survey_reminder,
    send_evening_summary,
)

app, _ = create_app("development")

with app.app_context():
    # 只為測試建立必要資料表（不跑遷移）
    try:
        db.create_all()
    except Exception as e:
        print(f"db.create_all() 跳過/失敗: {e}")

    print("Calling send_noon_care...")
    send_noon_care()

    print("Calling send_survey_reminder...")
    send_survey_reminder()

    print("Calling send_evening_summary...")
    send_evening_summary()

print("Done")
