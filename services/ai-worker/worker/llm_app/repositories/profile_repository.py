# llm_app/repositories/profile_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import func # 【新增】導入 func 以使用 now()
from ..models.chat_profile import SessionLocal, ChatUserProfile
from datetime import datetime
import json

class ProfileRepository:
    def _get_db(self) -> Session:
        return SessionLocal()

    def get_or_create_by_user_id(self, user_id: int, line_user_id: str = None) -> ChatUserProfile:
        """讀取 Profile，若不存在則建立一筆新的空紀錄。"""
        db = self._get_db()
        try:
            profile = db.query(ChatUserProfile).filter(ChatUserProfile.user_id == user_id).first()
            if not profile:
                print(f"[Profile Repo] 找不到 user_id={user_id} 的 Profile，將建立新紀錄。")
                profile = ChatUserProfile(
                    user_id=user_id,
                    line_user_id=line_user_id, # 使用傳入的 line_user_id
                    last_contact_ts=func.now()
                )
                db.add(profile)
                db.commit()
                db.refresh(profile)
            return profile
        finally:
            db.close()

    def read_profile_as_dict(self, user_id: str) -> dict:
        """讀取 Profile 並以字典格式回傳。"""
        profile = self.get_or_create_by_user_id(user_id)
        return {
            "personal_background": profile.profile_personal_background or {},
            "health_status": profile.profile_health_status or {},
            "life_events": profile.profile_life_events or {}
        }

    def update_profile_facts(self, user_id: int, facts_to_update: dict) -> None:
        """根據 Profiler 產生的指令集，安全地更新 Profile。"""
        if not facts_to_update or (not facts_to_update.get('add') and not facts_to_update.get('update') and not facts_to_update.get('remove')):
            # 【修正】修正日誌輸出中的變數名稱錯誤
            print(f"[Profile Repo] 無任何更新指令，跳過 {user_id} 的 Profile 更新。")
            return

        db = self._get_db()
        try:
            profile = db.query(ChatUserProfile).filter(ChatUserProfile.user_id == user_id).first()
            if not profile:
                print(f"[Profile Repo] 更新失敗，找不到 user_id={user_id} 的 Profile。")
                return

            # 【新增】一個旗標來追蹤是否有實際變動
            is_modified = True 

            # 處理 'add' 和 'update'
            for op in ['add', 'update']:
                for category_key, facts in facts_to_update.get(op, {}).items():
                    # 【修正】統一 category 命名，去除 profile_ 前綴
                    # Profiler 的輸出是 personal_background, health_status...
                    field_name = f"profile_{category_key}"
                    if hasattr(profile, field_name):
                        current_data = getattr(profile, field_name) or {}
                        
                        # 深度合併字典
                        def deep_merge(d1, d2):
                            for k, v in d2.items():
                                if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                                    d1[k] = deep_merge(d1[k], v)
                                else:
                                    d1[k] = v
                            return d1
                        
                        updated_data = deep_merge(dict(current_data), facts)
                        
                        # 【修改】簡化判斷邏輯
                        # 只要 LLM 輸出了 add 或 update 指令，我們就視為有修改意圖
                        # 並且直接賦值。SQLAlchemy 會處理後續的變更追蹤。
                        setattr(profile, field_name, updated_data)
                        is_modified = True

            # 處理 'remove'
            for key_to_remove in facts_to_update.get('remove', []):
                parts = key_to_remove.split('.')
                category_key = parts[0]
                field_name = f"profile_{category_key}"
                if hasattr(profile, field_name):
                    current_data = getattr(profile, field_name)
                    if current_data:
                        # 【修正】移除巢狀 key 的邏輯
                        temp_data = current_data
                        # 走訪路徑除了最後一個 key
                        for part in parts[1:-1]:
                            temp_data = temp_data.get(part)
                            if not isinstance(temp_data, dict):
                                temp_data = None
                                break
                        
                        # 如果路徑有效且最後的 key 存在，則刪除
                        if temp_data and isinstance(temp_data, dict) and parts[-1] in temp_data:
                            del temp_data[parts[-1]]
                            setattr(profile, field_name, current_data) # 將修改後的整個 JSON 寫回
                            is_modified = True

            if is_modified:
                profile.updated_at = func.now()
                db.commit()
                print(f"✅ [Profile Repo] 成功更新 user_id={user_id} 的 Profile。")
            else:
                print(f"ℹ️ [Profile Repo] user_id={user_id} 的 Profile 無需變動。")
        finally:
            db.close()

    def touch_last_contact_ts(self, user_id: str, line_user_id: str = None) -> None:
        """【修正】更新最後聯絡時間，確保在同一個 session 中完成。"""
        db = self._get_db()
        try:
            # 直接呼叫 get_or_create，它會處理創建或查找
            profile = self.get_or_create_by_user_id(user_id, line_user_id=line_user_id)
            # 更新時間
            profile.last_contact_ts = func.now()
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"❌ [Profile Repo] 更新 user_id={user_id} 的 last_contact_ts 失敗: {e}")
        finally:
            db.close()