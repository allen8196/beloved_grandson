# services/web-app/app/models/models.py
from ..extensions import db
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    account = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_staff = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    gender = db.Column(db.String(10))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    last_login = db.Column(db.DateTime)
    line_user_id = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    health_profile = db.relationship('HealthProfile', backref='user', foreign_keys='HealthProfile.user_id', uselist=False, cascade="all, delete-orphan")
    staff_details = db.relationship('StaffDetail', backref='user', uselist=False, cascade="all, delete-orphan")
    daily_metrics = db.relationship('DailyMetric', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    mmrc_questionnaires = db.relationship('QuestionnaireMMRC', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    cat_questionnaires = db.relationship('QuestionnaireCAT', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    # Relationship for staff managing health profiles
    managed_profiles = db.relationship('HealthProfile', foreign_keys='HealthProfile.staff_id', back_populates='managing_staff', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "account": self.account,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "is_staff": self.is_staff,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }

class HealthProfile(db.Model):
    __tablename__ = 'health_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    height_cm = db.Column(db.Integer)
    weight_kg = db.Column(db.Integer)
    smoke_status = db.Column(db.String(10)) # e.g., 'never', 'quit', 'current'
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    managing_staff = db.relationship('User', foreign_keys=[staff_id], back_populates='managed_profiles')

class StaffDetail(db.Model):
    __tablename__ = 'staff_details'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    title = db.Column(db.String(100)) # e.g., '呼吸治療師'

class DailyMetric(db.Model):
    __tablename__ = 'daily_metrics'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    water_cc = db.Column(db.Integer)
    medication = db.Column(db.Boolean)
    exercise_min = db.Column(db.Integer)
    cigarettes = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class QuestionnaireMMRC(db.Model):
    __tablename__ = 'questionnaire_mmrc'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    score = db.Column(db.SmallInteger, nullable=False)
    answer_text = db.Column(db.Text)
    record_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class QuestionnaireCAT(db.Model):
    __tablename__ = 'questionnaire_cat'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    cough_score = db.Column(db.SmallInteger, nullable=False)
    phlegm_score = db.Column(db.SmallInteger, nullable=False)
    chest_score = db.Column(db.SmallInteger, nullable=False)
    breath_score = db.Column(db.SmallInteger, nullable=False)
    limit_score = db.Column(db.SmallInteger, nullable=False)
    confidence_score = db.Column(db.SmallInteger, nullable=False)
    sleep_score = db.Column(db.SmallInteger, nullable=False)
    energy_score = db.Column(db.SmallInteger, nullable=False)
    total_score = db.Column(db.SmallInteger, nullable=False)
    record_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))