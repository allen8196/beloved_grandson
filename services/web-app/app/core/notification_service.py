# services/web-app/app/core/notification_service.py
import pika
import os
import json
import threading
import time
import logging
from app.extensions import socketio
from app.core.chat_repository import ChatRepository

def message_callback(ch, method, properties, body):
    """
    Callback function to process messages from RabbitMQ.
    This is defined at the top level so it can be imported for testing.
    """
    print(f" [x] Received notification: {body.decode()}", flush=True)
    try:
        message = json.loads(body)

        if 'user_transcript' not in message or 'ai_response' not in message:
            raise ValueError("Missing required fields in notification message")

        # Save to chat history
        chat_repo = ChatRepository()
        conversation_id = chat_repo.create_conversation(
            patient_id=message.get("patient_id"),
            therapist_id=message.get("therapist_id")
        )

        # Add user message
        chat_repo.add_chat_message({
            "conversation_id": conversation_id,
            "sender_type": "user",
            "content": message.get("user_transcript"),
        })

        # Add AI message
        chat_repo.add_chat_message({
            "conversation_id": conversation_id,
            "sender_type": "ai",
            "content": message.get("ai_response"),
            "audio_url": message.get("response_audio_url")
        })

        print(f" [>] Emitting notification via WebSocket: {message}", flush=True)
        socketio.emit('notification', message)

    except (json.JSONDecodeError, ValueError) as e:
        logging.error(f"Invalid message format or Failed to decode JSON: {e}")
    except Exception as e:
        logging.error(f" [!] Error processing message: {e}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_notification_listener():
    """
    Starts the RabbitMQ listener in a background thread.
    """
    thread = threading.Thread(target=listen_for_notifications)
    thread.daemon = True
    thread.start()

def listen_for_notifications():
    """
    Connects to RabbitMQ and listens for notifications from the ai-worker.
    """
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    notification_queue = os.environ.get("RABBITMQ_NOTIFICATION_QUEUE", "notifications_queue")

    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue=notification_queue, durable=True)
            print(' [*] Waiting for notifications. To exit press CTRL+C')

            channel.basic_consume(queue=notification_queue, on_message_callback=message_callback)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            print(f"Connection to RabbitMQ failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Restarting listener...")
            time.sleep(5)
