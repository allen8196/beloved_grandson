import os
import pika
import json
import uuid
import time
import pytest
from minio import Minio
from minio.error import S3Error

# --- RabbitMQ RPC Client ---
class TtsRpcClient:
    def __init__(self):
        self.rabbitmq_host = os.environ.get("RABBITMQ_HOST", "localhost")
        self.tts_queue = os.environ.get("RABBITMQ_TTS_QUEUE", "tts_request_queue")
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

    def call(self, text: str):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        request_payload = json.dumps({"text": text})
        
        self.channel.basic_publish(
            exchange='',
            routing_key=self.tts_queue,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=request_payload
        )
        
        self.connection.process_data_events(time_limit=10)

        if self.response is None:
            raise TimeoutError("TTS service RPC request timed out")
            
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

# --- Test Case ---
def test_tts_rpc_call(minio_client):
    """
    Tests the full RPC call to the TTS service.
    """
    test_text = "Hello, this is a test for the TTS service."
    tts_client = None
    object_name = None
    bucket_name = os.environ.get("MINIO_BUCKET_NAME", "audio-bucket")

    try:
        tts_client = TtsRpcClient()
        print(f"Sending RPC request with text: '{test_text}'...")
        response = tts_client.call(test_text)
        
        assert "object_name" in response
        object_name = response["object_name"]
        assert isinstance(object_name, str)
        assert object_name.endswith(".mp3")
        print(f"Received object_name: {object_name}")

        # Verify the object exists in MinIO
        try:
            minio_client.stat_object(bucket_name, object_name)
            print(f"Verified object {object_name} exists in bucket {bucket_name}.")
        except S3Error as exc:
            pytest.fail(f"Could not find object {object_name} in MinIO. Error: {exc}")

    except pika.exceptions.AMQPConnectionError as e:
        pytest.fail(f"Failed to connect to RabbitMQ: {e}")
    except TimeoutError as e:
        pytest.fail(f"RPC call timed out: {e}")
    finally:
        if tts_client:
            tts_client.close()
        # Cleanup the created object from MinIO
        if object_name:
            try:
                minio_client.remove_object(bucket_name, object_name)
                print(f"Cleaned up object {object_name} from bucket {bucket_name}.")
            except S3Error as exc:
                print(f"Failed to cleanup object {object_name}: {exc}")
