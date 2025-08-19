# llm_app/models/chat_profile.py
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import os

# 建立一個獨立的 SQLAlchemy 連線，專供聊天機器人 Profile 使用
# 這樣可以避免與主框架的 Flask-SQLAlchemy 實例產生衝突
DATABASE_URL = "postgresql://{user}:{password}@{host}:{port}/{dbname}".format(
    user=os.getenv('POSTGRES_USER', 'postgres'),
    password=os.getenv('POSTGRES_PASSWORD', ''),
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=os.getenv('POSTGRES_PORT', '5432'),
    dbname=os.getenv('POSTGRES_DB', 'senior_health'),
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ChatUserProfile(Base):
    __tablename__ = 'chat_user_profiles'
    
    line_user_id = Column(String, primary_key=True, index=True)
    profile_personal_background = Column(JSONB)
    profile_health_status = Column(JSONB)
    profile_life_events = Column(JSONB)
    last_contact_ts = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

def create_profile_table_if_not_exists():
    """在應用啟動時確保表格存在"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ [Profile DB] ChatUserProfile 表格已確認存在。")
    except Exception as e:
        print(f"❌ [Profile DB] 建立 ChatUserProfile 表格失敗: {e}")