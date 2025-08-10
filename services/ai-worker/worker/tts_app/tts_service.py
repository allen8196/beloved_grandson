import os
import uuid
from minio import Minio
import io
from minio.error import S3Error
from mutagen import File

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

        # TODO: 將 `text` 參數轉換成音訊檔案，上傳到 MinIO，輸出物件名稱和音訊長度。

        try:
            local_audio_path = "Anya_music.m4a"
            # 檢查檔案是否存在，以避免錯誤
            if not os.path.exists(local_audio_path):
                raise FileNotFoundError(f"指定的音檔不存在: {local_audio_path}")
            audio_data_len = os.path.getsize(local_audio_path)

            metadata = {}
            duration_ms = 0
            try:
                audio_file = File(local_audio_path)
                duration_ms = int(audio_file.info.length * 1000)
                metadata['duration-ms'] = str(duration_ms)
            except Exception as e:
                print(f"無法使用 mutagen 解析音訊檔案: {e}")

            # 產生唯一的物件名稱
            object_name = f"{uuid.uuid4()}.m4a"

            # 上傳到 MinIO
            print(f"Uploading {object_name} to bucket {self.bucket_name}...", flush=True)
            with open(local_audio_path, 'rb') as audio_file:
                self.minio_client.put_object(
                    self.bucket_name,
                    object_name,
                    audio_file,
                    length=audio_data_len,
                    content_type='audio/mpeg',
                    metadata=metadata
                )

            print(f"Successfully uploaded {object_name}, {duration_ms}.", flush=True)
            return object_name, duration_ms

        except S3Error as exc:
            print(f"Error uploading to MinIO: {exc}", flush=True)
            raise

_tts_service_instance = TTSService()

def get_tts_service() -> TTSService:
    """Factory function to get the TTSService instance."""
    return _tts_service_instance

if __name__ == "__main__":
    # 測試 TTSService

    # 0. .env.example 改成 .env ，可以不做任何設定

    # 1. 啟動ai-worker和相關的容器
    # docker-compose -f docker-compose.dev.yml up -d --build ai-worker

    # 2. 執行測試腳本
    # docker-compose -f docker-compose.dev.yml exec ai-worker python worker/tts_app/tts_service.py

    # 3. 修改 TODO 部分以實現文字合成和上傳到 MinIO 的邏輯。

    # 4. 查看結果
    # 合成的音訊已上傳為：e069d6cd-1def-4e36-bf03-82ebd8ae3bea.m4a
    # 音訊長度：3820 毫秒
    # 4.1 連線進入 MinIO 瀏覽器（例如：http://localhost:9001），檢查名為 'audio-bucket' 的 bucket，是否有檔案。

    try:
        # 我們使用全域定義的實例，這與 get_tts_service() 的方式相似。
        tts_service = _tts_service_instance
        test_text = "This is a test synthesis."
        print(f"正在合成文字：'{test_text}'")

        object_name, duration_ms = tts_service.synthesize_text(test_text)

        print("\n--- 測試結果 ---")
        print(f"合成的音訊已上傳為：{object_name}")
        print(f"音訊長度：{duration_ms} 毫秒")
        print("測試成功結束。")

        print(f"\n若要驗證，請在您的 MinIO 實例中（例如：http://localhost:9001）檢查名為 '{tts_service.bucket_name}' 的 bucket。")

    except FileNotFoundError as e:
        print(f"\n發生錯誤：{e}")
        print("請確保 'Anya_music.m4a' 檔案存在於 'ai-worker' 目錄中。")
    except Exception as e:
        print(f"\n測試過程中發生錯誤：{e}")
