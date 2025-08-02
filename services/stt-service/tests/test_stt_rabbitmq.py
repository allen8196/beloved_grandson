import os
import pika
import json
import uuid
import time
import pytest
from minio import Minio
from minio.error import S3Error

# --- RabbitMQ RPC Client (similar to the one in ai-worker) ---
class SttRpcClient:
    def __init__(self):
        self.rabbitmq_host = os.environ.get("RABBITMQ_HOST", "localhost")
        self.stt_queue = os.environ.get("RABBITMQ_STT_QUEUE", "stt_request_queue")
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.rabbitmq_host))
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue
        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True
        )
        self.response = None
        self.corr_id = None

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, bucket_name: str, object_name: str):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        request_payload = json.dumps({
            "bucket_name": bucket_name,
            "object_name": object_name
        })
        
        self.channel.basic_publish(
            exchange='',
            routing_key=self.stt_queue,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=request_payload
        )
        
        # Wait for the response with a timeout
        self.connection.process_data_events(time_limit=10) # 10 seconds timeout

        if self.response is None:
            raise TimeoutError("STT service RPC request timed out")
            
        return json.loads(self.response)

    def close(self):
        self.connection.close()

# --- MinIO Fixture ---
@pytest.fixture(scope="module")
def minio_client():
    client = Minio(
        os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.environ.get("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.environ.get("MINIO_SECRET_KEY", "minioadmin"),
        secure=False
    )
    return client

@pytest.fixture(scope="module")
def setup_minio(minio_client):
    bucket_name = "test-stt-bucket"
    object_name = "Anya_music.mp3"
    # Use the absolute path to the project root to find the audio file
    audio_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../Anya_music.mp3"))

    try:
        found = minio_client.bucket_exists(bucket_name)
        if not found:
            minio_client.make_bucket(bucket_name)
        
        minio_client.fput_object(
            bucket_name, object_name, audio_file_path
        )
        print(f"Uploaded {object_name} to bucket {bucket_name}")
    except S3Error as exc:
        pytest.fail(f"MinIO setup failed: {exc}")

    yield bucket_name, object_name

    # Teardown
    try:
        minio_client.remove_object(bucket_name, object_name)
        minio_client.remove_bucket(bucket_name)
        print(f"Cleaned up bucket {bucket_name}")
    except S3Error as exc:
        print(f"MinIO cleanup failed: {exc}")


# --- Test Case ---
def test_stt_rpc_call(setup_minio):
    """
    Tests the full RPC call to the STT service.
    """
    bucket_name, object_name = setup_minio
    
    stt_client = None
    try:
        stt_client = SttRpcClient()
        print(f"Sending RPC request for {bucket_name}/{object_name}...")
        response = stt_client.call(bucket_name, object_name)
        
        assert "transcribed_text" in response
        assert response["transcribed_text"] == f"transcribed_{object_name}"
        print(f"Received expected response: {response}")

    except pika.exceptions.AMQPConnectionError as e:
        pytest.fail(f"Failed to connect to RabbitMQ: {e}")
    except TimeoutError as e:
        pytest.fail(f"RPC call timed out: {e}")
    finally:
        if stt_client:
            stt_client.close()
