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

            # 這裡可以加入實際的 STT 處理邏輯
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
