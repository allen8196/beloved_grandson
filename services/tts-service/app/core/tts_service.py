import os
import uuid
from minio import Minio
from minio.error import S3Error
import io

class TTSService:
    def __init__(self):
        self.minio_client = Minio(
            os.environ.get("MINIO_ENDPOINT", "minio:9000"),
            access_key=os.environ.get("MINIO_ACCESS_KEY"),
            secret_key=os.environ.get("MINIO_SECRET_KEY"),
            secure=False
        )
        self.bucket_name = os.environ.get("MINIO_BUCKET_NAME", "audio-bucket")
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensures the MinIO bucket exists."""
        try:
            found = self.minio_client.bucket_exists(self.bucket_name)
            if not found:
                self.minio_client.make_bucket(self.bucket_name)
                print(f"Bucket '{self.bucket_name}' created.", flush=True)
        except S3Error as exc:
            print(f"Error checking or creating bucket: {exc}", flush=True)
            raise

    def synthesize_text(self, text: str) -> str:
        """
        Synthesizes text into an audio file and uploads it to MinIO.
        This is a placeholder implementation.
        """
        try:
            local_audio_path = "Anya_music.mp3"
            # 檢查檔案是否存在，以避免錯誤
            if not os.path.exists(local_audio_path):
                raise FileNotFoundError(f"指定的音檔不存在: {local_audio_path}")
            audio_data_len = os.path.getsize(local_audio_path)

            # 產生唯一的物件名稱
            object_name = f"{uuid.uuid4()}.mp3"

            # 上傳到 MinIO
            print(f"Uploading {object_name} to bucket {self.bucket_name}...", flush=True)
            with open(local_audio_path, 'rb') as audio_file:
                self.minio_client.put_object(
                    self.bucket_name,
                    object_name,
                    audio_file,
                    length=audio_data_len,
                    content_type='audio/mpeg'
                )

            print(f"Successfully uploaded {object_name}.", flush=True)
            return object_name

        except S3Error as exc:
            print(f"Error uploading to MinIO: {exc}", flush=True)
            raise

_tts_service_instance = TTSService()

def get_tts_service() -> TTSService:
    """Factory function to get the TTSService instance."""
    return _tts_service_instance
