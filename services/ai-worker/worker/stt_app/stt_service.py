import os
from minio import Minio
from minio.error import S3Error

class STTService:
    def __init__(self):
        self.minio_client = Minio(
            os.environ.get("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.environ.get("MINIO_ACCESS_KEY"),
            secret_key=os.environ.get("MINIO_SECRET_KEY"),
            secure=False
        )

    def transcribe_audio(self, bucket_name: str, object_name: str) -> str:
        """
        Downloads an audio file from MinIO and transcribes it.
        This is a placeholder implementation.
        """
        try:
            # 從 MinIO 下載音檔
            print(f"從 MinIO 下載檔案: {bucket_name}/{object_name}", flush=True)
            audio_data = self.minio_client.get_object(bucket_name, object_name)

            # TODO 這裡可以加入實際的 STT 處理邏輯
            # 例如，將 audio_data.read() 傳遞給 STT 模型

            # 為了測試，我們模擬轉錄並回傳檔案名稱
            print(f"模擬語音轉文字處理: {object_name}", flush=True)
            transcribed_text = f"transcribed_{object_name}"

            return transcribed_text
        except S3Error as exc:
            print(f"從 MinIO 下載檔案時發生錯誤: {exc}", flush=True)
            raise

_stt_service_instance = STTService()

def get_stt_service() -> STTService:
    """Factory function to get the STTService instance."""
    return _stt_service_instance

if __name__ == "__main__":
    print("執行 STTService 測試...")

    # 說明：
    # 0. .env.example 改成 .env ，可以不做任何設定

    # 1. 啟動ai-worker和相關的容器
    # docker-compose -f docker-compose.dev.yml up -d --build ai-worker

    # 連線進入 MinIO 瀏覽器（例如：http://localhost:9001），新增名子是 'audio-uploads' 的 bucket，將音檔上傳。

    # 2. 執行測試腳本
    # docker-compose -f docker-compose.dev.yml exec ai-worker python worker/stt_app/stt_service.py

    # --- 測試程式碼 ---
    stt_service = get_stt_service()
    bucket_name = "audio-uploads"
    object_name = "1_6f2d14ac-8d52-4c15-8ee4-f191215b8a52.m4a"

    try:
        transcribed_text = stt_service.transcribe_audio(bucket_name, object_name)
        print(f"   => 輸出結果: '{transcribed_text}'")
    except Exception as e:
        print(f"   [錯誤] 執行 transcribe_audio 時失敗: {e}")
        print("--- 測試終止 ---")

    print("--- STTService 整合測試完成 ---")
