# services/web-app/app/core/line_service.py
import os
from flask import current_app
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    # 引用 PushMessageRequest 來主動推播訊息
    PushMessageRequest,
    TextMessage,
    # 引用 linebot.v3.messaging.MessagingApiBlob 來處理媒體內容
    MessagingApiBlob,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent,
    UnfollowEvent,
    AudioMessageContent
)

# --- Service Singleton (服務單例模式) ---
# 全域變數，用來存放 LineService 的單一實例
_line_service = None

def get_line_service():
    """
    工廠函式，用於獲取 LineService 的單例實例。
    確保整個應用程式中只有一個 LineService 物件。
    """
    global _line_service
    if _line_service is None:
        # 如果實例不存在，則創建一個新的
        _line_service = LineService(
            # 從 Flask 的設定檔中讀取 LINE Channel Secret
            channel_secret=current_app.config['LINE_CHANNEL_SECRET'],
            # 從 Flask 的設定檔中讀取 LINE Channel Access Token
            channel_access_token=current_app.config['LINE_CHANNEL_ACCESS_TOKEN']
            # TODO: 未來可在此注入其他服務，例如 RabbitMQ, Minio, Repositories 等
        )
    return _line_service

# --- Core Service Class (核心服務類別) ---
class LineService:
    """
    處理所有與 LINE 平台互動相關的業務邏輯。
    """
    def __init__(self, channel_secret: str, channel_access_token: str):
        # 初始化 Webhook 處理器，需要 channel_secret 來驗證 LINE 送來的請求簽名
        self.handler = WebhookHandler(channel_secret)
        # 初始化 API 設定，需要 channel_access_token 才能代表 Bot 主動發送訊息
        self.configuration = Configuration(access_token=channel_access_token)
        # 註冊所有事件的處理函式
        self._register_handlers()

    # ... (handle_webhook, _get_or_create_conversation, _register_handlers,
    #      handle_text_message, handle_audio_message, handle_follow, handle_unfollow,
    #      link_rich_menu_to_user, _reply_text, _reply_with_registration_prompt
    #      等函式維持不變) ...

    def handle_webhook(self, body: str, signature: str):
        """
        處理從 LINE 平台傳來的 Webhook 請求。
        :param body: 請求的原始內容 (JSON 字串)
        :param signature: X-Line-Signature 標頭，用於驗證請求來源
        """
        # 使用 handler 處理請求，它會自動驗證簽名並呼叫對應的事件處理函式
        self.handler.handle(body, signature)

    def _get_or_create_conversation(self, patient_id: int) -> str:
        """
        尋找指定病患最近的活躍對話，如果沒有或已過期，則創建一個新的對話。
        一個對話如果在過去 24 小時內開始，則被視為「活躍」。
        :param patient_id: 病患的內部資料庫 ID
        :return: 對話的 ID (字串格式)
        """
        # 延遲導入，避免循環依賴問題
        from .chat_repository import ChatRepository
        from datetime import datetime, timezone, timedelta

        chat_repo = ChatRepository()
        # 從資料庫中根據病患ID獲取最近的對話紀錄
        recent_conversations = chat_repo.get_conversations_by_patient_id(patient_id=patient_id)

        if recent_conversations:
            latest_convo = recent_conversations[0]
            # 確保從資料庫取出的時間是帶有時區資訊的 (UTC)
            start_time_aware = latest_convo['start_time'].replace(tzinfo=timezone.utc)

            # 檢查最新的對話是否仍在 24 小時內
            if datetime.now(timezone.utc) - start_time_aware < timedelta(hours=24):
                # 如果是，回傳該對話的 ID
                return str(latest_convo['_id'])

        # 如果找不到活躍的對話，就創建一個新的
        new_conversation_id = chat_repo.create_conversation(patient_id=patient_id)
        return str(new_conversation_id)

    def _register_handlers(self):
        """註冊 WebhookHandler 的所有事件處理函式。"""

        # 註冊「文字訊息」事件處理器
        @self.handler.add(MessageEvent, message=TextMessageContent)
        def handle_text_message(event: MessageEvent):
            from .user_repository import UserRepository
            from .chat_repository import ChatRepository
            from .rabbitmq_service import get_rabbitmq_service

            user_repo = UserRepository()
            # 根據 LINE User ID 在我方資料庫中尋找使用者
            user = user_repo.find_by_line_user_id(event.source.user_id)

            if not user:
                # 如果使用者未註冊，回覆提示註冊的訊息
                self._reply_with_registration_prompt(event.reply_token)
                return

            try:
                # 獲取或創建一個對話
                conversation_id = self._get_or_create_conversation(user.id)
                chat_repo = ChatRepository()
                # 將使用者傳來的訊息存入資料庫
                chat_repo.add_chat_message({
                    "conversation_id": conversation_id,
                    "sender_type": 'user',  # 發送者是使用者
                    "content": event.message.text,
                    "metadata": {'line_message_id': event.message.id} # 紀錄 LINE 的訊息 ID
                })

                # 取得 RabbitMQ 服務
                rabbitmq_service = get_rabbitmq_service()
                # 從環境變數讀取任務隊列名稱，預設為 'task_queue'
                task_queue_name = os.environ.get("RABBITMQ_QUEUE", "task_queue")
                # 發布一個任務到 RabbitMQ，讓後端 worker 進行非同步處理
                rabbitmq_service.publish_message(
                    queue_name=task_queue_name,
                    message_body={'patient_id': user.id, 'text': event.message.text}
                )

                # 回覆使用者，告知訊息已收到並正在處理
                self._reply_text(event.reply_token, "我們已收到您的訊息，AI 正在處理中。")
            except Exception as e:
                current_app.logger.error(f"處理使用者 {user.id} 的文字訊息時發生錯誤: {e}", exc_info=True)

        # 註冊「語音訊息」事件處理器
        @self.handler.add(MessageEvent, message=AudioMessageContent)
        def handle_audio_message(event: MessageEvent):
            from .user_repository import UserRepository
            from .chat_repository import ChatRepository
            from .rabbitmq_service import get_rabbitmq_service
            from .minio_service import get_minio_service
            import uuid
            import io
            from mutagen import File

            user_repo = UserRepository()
            user = user_repo.find_by_line_user_id(event.source.user_id)

            if not user:
                # 對於未註冊使用者傳來的語音，僅記錄 log，不予處理
                current_app.logger.info(f"收到來自未註冊使用者 {event.source.user_id} 的語音訊息")
                return

            try:
                # 使用 ApiClient 下載語音檔案內容
                with ApiClient(self.configuration) as api_client:
                    line_bot_blob_api = MessagingApiBlob(api_client)
                    # 透過 message ID 從 LINE 伺服器獲取語音檔案的二進位內容
                    message_content = line_bot_blob_api.get_message_content(event.message.id)

                # --- 使用 mutagen 計算音訊時長 ---

                duration_ms = 0
                try:
                    audio_file = File(io.BytesIO(message_content))
                    duration_ms = int(audio_file.info.length * 1000)
                except Exception as e:
                    current_app.logger.warning(f"無法使用 mutagen 解析音訊檔案: {e}")

                # --- 上傳到 MinIO 並附上元數據 ---
                minio_service = get_minio_service()
                bucket_name = 'audio-uploads'
                object_name = f"{user.id}_{uuid.uuid4()}.m4a"
                metadata = {}
                if duration_ms > 0:
                    metadata['duration-ms'] = str(duration_ms)

                # 將語音檔案內容上傳到 Minio 物件儲存
                minio_service.upload_file_content(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    data=message_content,
                    length=len(message_content),
                    content_type='audio/mp4',
                    metadata=metadata
                )

                # --- 儲存聊天記錄並發布任務 ---
                conversation_id = self._get_or_create_conversation(user.id)
                chat_repo = ChatRepository()
                chat_repo.add_chat_message({
                    "conversation_id": conversation_id,
                    "sender_type": 'user',
                    "content": f"Audio message: {object_name}",
                    "metadata": {
                        'line_message_id': event.message.id,
                        'minio_object_name': object_name,
                        'minio_bucket': bucket_name,
                        'duration_ms': duration_ms # 將時長也存入聊天記錄
                    }
                })

                rabbitmq_service = get_rabbitmq_service()
                task_queue_name = os.environ.get("RABBITMQ_QUEUE", "task_queue")

                message_body = {
                    'patient_id': user.id,
                    'object_name': object_name,
                    'bucket_name': bucket_name,
                    'duration_ms': duration_ms # 將時長傳遞給 ai-worker
                }
                rabbitmq_service.publish_message(
                    queue_name=task_queue_name,
                    message_body=message_body
                )
            except Exception as e:
                current_app.logger.error(f"處理使用者 {user.id} 的語音訊息時發生錯誤: {e}", exc_info=True)
                self._reply_text(event.reply_token, "抱歉，處理您的語音訊息時發生錯誤，請稍後再試。")

        # 註冊「關注」(Follow / Add Friend) 事件處理器
        @self.handler.add(FollowEvent)
        def handle_follow(event: FollowEvent):
            from .user_repository import UserRepository
            user_repo = UserRepository()
            line_user_id = event.source.user_id
            current_app.logger.info(f"Received follow event for LINE user ID: {line_user_id}")

            user = user_repo.find_by_line_user_id(line_user_id)

            if user:
                current_app.logger.info(f"Found existing user (ID: {user.id}) for LINE user ID: {line_user_id}. Applying MEMBER menu.")
                # 如果使用者已存在於系統中，為他綁定「已註冊會員」的 Rich Menu
                self.link_rich_menu_to_user(line_user_id, rich_menu_id=current_app.config.get('LINE_RICH_MENU_ID_MEMBER'))
            else:
                current_app.logger.info(f"No existing user found for LINE user ID: {line_user_id}. Applying GUEST menu.")
                # 如果使用者不存在，為他綁定「未註冊會員」的 Rich Menu
                self.link_rich_menu_to_user(line_user_id, current_app.config.get('LINE_RICH_MENU_ID_GUEST'))

            # 回覆歡迎訊息
            self._reply_text(event.reply_token, "歡迎使用「健康陪跑」！點擊下方選單開始互動。")

        # # 註冊「取消關注」(Unfollow / Block) 事件處理器
        @self.handler.add(UnfollowEvent)
        def handle_unfollow(event: UnfollowEvent):
            from .user_repository import UserRepository
            user_repo = UserRepository()
            user = user_repo.find_by_line_user_id(event.source.user_id)
            current_app.logger.info(f"使用者 {user.id} 封鎖或刪除官方帳號")

    def link_rich_menu_to_user(self, user_id: str, rich_menu_id: str):
        """將指定的 Rich Menu (圖文選單) 綁定到特定使用者"""
        if not rich_menu_id:
            # 如果設定檔中沒有 Rich Menu ID，則記錄警告並返回
            current_app.logger.warning("嘗試綁定 Rich Menu，但未設定 ID。")
            return
        try:
            # 呼叫 LINE API 將 Rich Menu 綁定到使用者
            with ApiClient(self.configuration) as api_client:
                MessagingApi(api_client).link_rich_menu_id_to_user(user_id, rich_menu_id)
            current_app.logger.info(f"已將 Rich Menu {rich_menu_id} 綁定至使用者 {user_id}。")
        except Exception as e:
            current_app.logger.error(f"為使用者 {user_id} 綁定 Rich Menu 失敗: {e}")

    def _reply_text(self, reply_token: str, text: str):
        """一個私有的輔助函式，用來快速回覆純文字訊息"""
        with ApiClient(self.configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=text)]
                )
            )

    def _reply_with_registration_prompt(self, reply_token: str):
        self._reply_text(reply_token, "您好，請點擊下方選單完成註冊，即可開始使用我們的服務。")

    def push_text_message(self, user_id: int, text: str):
        """
        透過我方資料庫的 user_id 主動推播文字訊息給指定使用者。
        """
        from .user_repository import UserRepository
        user_repo = UserRepository()
        user = user_repo.find_by_id(user_id)

        if not user or not user.line_user_id:
            current_app.logger.warning(f"嘗試推播訊息給使用者 {user_id}，但找不到對應的 LINE 使用者 ID。")
            return

        try:
            with ApiClient(self.configuration) as api_client:
                # 建立一個 PushMessageRequest 物件
                push_message_request = PushMessageRequest(
                    to=user.line_user_id,
                    messages=[TextMessage(text=text)]
                )
                # 呼叫 push_message 並傳入建立好的 request 物件
                MessagingApi(api_client).push_message(push_message_request)

            current_app.logger.info(f"成功推播訊息給使用者 {user_id}。")
        except Exception as e:
            # 在 log 中也記錄下 user.line_user_id，方便追蹤是哪個 LINE 帳號出錯
            current_app.logger.error(f"推播訊息至使用者 {user_id} (LINE ID: {user.line_user_id}) 失敗: {e}")

    def push_audio_message(self, user_id: int, object_name: str, duration: int = 60000):
        """
        透過我方資料庫的 user_id 主動推播音訊訊息給指定使用者。
        """
        #TODO: 產生一個有時效性的預簽章 URL
        from .user_repository import UserRepository
        from linebot.v3.messaging import AudioMessage

        user_repo = UserRepository()
        user = user_repo.find_by_id(user_id)

        if not user or not user.line_user_id:
            current_app.logger.warning(f"嘗試推播音訊給使用者 {user_id}，但找不到對應的 LINE 使用者 ID。")
            return

        # 從環境變數讀取應用程式的公開域名
        BASE_URL = os.environ.get('BASE_URL')
        if not BASE_URL:
            current_app.logger.error("環境變數 DOMAIN_NAME 未設定，無法產生公開音訊 URL。")
            return

        bucket_name = 'audio-bucket'
        # 直接組合公開的 URL，格式為 https://<你的域名>/<儲存桶名>/<物件名>
        audio_url = f"{BASE_URL}/{bucket_name}/{object_name}"
        try:
            with ApiClient(self.configuration) as api_client:
                push_message_request = PushMessageRequest(
                    to=user.line_user_id,
                    messages=[
                        AudioMessage(
                            originalContentUrl=audio_url,
                            duration=duration
                        )
                    ]
                )
                MessagingApi(api_client).push_message(push_message_request)

            current_app.logger.info(f"成功推播音訊訊息給使用者 {user_id}。")
        except Exception as e:
            current_app.logger.error(f"推播音訊至使用者 {user_id} (LINE ID: {user.line_user_id}) 失敗: {e}")
