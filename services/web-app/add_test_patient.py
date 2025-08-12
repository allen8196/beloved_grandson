from app.app import create_app
from app.extensions import db
from app.models.models import User


def main():
    app, _ = create_app("development")
    with app.app_context():
        line_user_id = "U58ec6cb491dfda6b5953ecb3cae06478"
        user = User(
            account="patient_manual_001",
            first_name="手動",
            last_name="測試",
            gender="male",
            line_user_id=line_user_id,
            is_staff=False,
            is_admin=False,
        )
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        print(f"Created test patient id={user.id}, line_user_id={line_user_id}")


if __name__ == "__main__":
    main()
