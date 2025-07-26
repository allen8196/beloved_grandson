import os
import requests
import boto3
import pika
import json
import time

def publish_notification(message: dict):
    """Publishes a message to the notification queue."""
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    notification_queue = os.environ.get("RABBITMQ_NOTIFICATION_QUEUE", "notifications_queue")

    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
        channel = connection.channel()
        channel.queue_declare(queue=notification_queue, durable=True)

        channel.basic_publish(
            exchange='',
            routing_key=notification_queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ))
        print(f"Sent notification: {message}", flush=True)
        connection.close()
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error connecting to RabbitMQ: {e}", flush=True)
        raise

def process_text_task(text_message: str):
    """
    Processes a text message by calling the llm-service.
    """
    llm_service_url = os.environ.get("LLM_SERVICE_URL", "http://llm-service:8000")

    try:
        response = requests.post(
            f"{llm_service_url}/api/v1/chat",
            json={"text": text_message},
            timeout=10
        )
        response.raise_for_status()
        print(f"Successfully called LLM Service. Response: {response.json()}", flush=True)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling LLM Service: {e}", flush=True)
        raise

def process_audio_task(bucket_name: str, object_name: str):
    """
    Processes an audio file task.
    1. Downloads the audio file from MinIO.
    2. Sends it to the STT service for transcription.
    3. Sends the transcribed text to the LLM service.
    4. Sends the LLM response to the TTS service.
    5. Publishes a completion notification.
    """
    # --- Service URLs and MinIO Config from Environment Variables ---
    stt_service_url = os.environ.get("STT_SERVICE_URL", "http://stt-service:8000")
    llm_service_url = os.environ.get("LLM_SERVICE_URL", "http://llm-service:8000")
    tts_service_url = os.environ.get("TTS_SERVICE_URL", "http://tts-service:8000")
    minio_endpoint_url = os.environ.get("MINIO_ENDPOINT_URL", "http://minio:9000")
    minio_access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

    try:
        # 1. Download audio from MinIO
        print(f"Downloading {object_name} from bucket {bucket_name}...", flush=True)
        s3_client = boto3.client(
            's3',
            endpoint_url=minio_endpoint_url,
            aws_access_key_id=minio_access_key,
            aws_secret_access_key=minio_secret_key,
            config=boto3.session.Config(signature_version='s3v4')
        )
        audio_object = s3_client.get_object(Bucket=bucket_name, Key=object_name)
        audio_bytes = audio_object['Body'].read()
        print("File downloaded successfully.", flush=True)

        # 2. Send to STT service
        print("Sending audio to STT service...", flush=True)
        files = {'audio_file': (object_name, audio_bytes, 'application/octet-stream')}
        stt_response = requests.post(
            f"{stt_service_url}/api/v1/transcribe",
            files=files,
            timeout=30 # Transcription can take longer
        )
        stt_response.raise_for_status()
        transcribed_text = stt_response.json()["transcribed_text"]
        print(f"STT service returned: '{transcribed_text}'", flush=True)

        # 3. Send transcribed text to LLM service
        print("Sending transcribed text to LLM service...", flush=True)
        llm_response_json = process_text_task(transcribed_text)
        llm_text_response = llm_response_json.get("response", "") # Assuming the key is "response"

        # 4. Send LLM response to TTS service
        if llm_text_response:
            print("Sending LLM response to TTS service...", flush=True)
            tts_response = requests.post(
                f"{tts_service_url}/api/v1/synthesize",
                json={"text": llm_text_response},
                timeout=30
            )
            tts_response.raise_for_status()
            tts_result = tts_response.json()
            print(f"TTS service returned: {tts_result}", flush=True)

            # 5. Publish completion notification
            notification_message = {
                "status": "completed",
                "original_file": object_name,
                "transcribed_text": transcribed_text,
                "llm_response": llm_text_response,
                "tts_output_url": tts_result.get("audio_url") # Assuming TTS returns a URL
            }
            publish_notification(notification_message)

        return llm_response_json

    except Exception as e:
        print(f"An error occurred in the audio processing pipeline: {e}", flush=True)
        raise


# This is a placeholder for the main loop that would consume from RabbitMQ
if __name__ == '__main__':
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    task_queue = os.environ.get("RABBITMQ_QUEUE", "task_queue")

    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue=task_queue, durable=True)
            print(' [*] AI Worker waiting for messages. To exit press CTRL+C', flush=True)

            def callback(ch, method, properties, body):
                task_data = json.loads(body)
                print(f"\n [x] Received task from {method.routing_key}: {task_data}", flush=True)

                try:
                    # Differentiate task based on content
                    if 'text' in task_data:
                        print(f" [*] Starting text processing task...", flush=True)
                        process_text_task(task_data['text'])
                    elif 'bucket_name' in task_data and 'object_name' in task_data:
                        print(f" [*] Starting audio processing task...", flush=True)
                        process_audio_task(task_data['bucket_name'], task_data['object_name'])
                    else:
                        print(f" [!] Unknown task format: {task_data}", flush=True)

                    print(f" [✔] Task completed successfully.", flush=True)
                except Exception as e:
                    print(f" [!] Error processing task: {e}", flush=True)

                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=task_queue, on_message_callback=callback)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            print(f"Connection to RabbitMQ failed: {e}. Retrying in 5 seconds...", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Restarting consumer...", flush=True)
            time.sleep(5)
