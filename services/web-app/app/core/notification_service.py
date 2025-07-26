# services/web-app/app/core/notification_service.py
import pika
import os
import json
import threading
from app.utils.extensions import socketio

def start_notification_listener():
    """
    在一個背景執行緒中啟動 RabbitMQ 的監聽器。
    """
    thread = threading.Thread(target=listen_for_notifications)
    thread.daemon = True
    thread.start()

def listen_for_notifications():
    """
    連接到 RabbitMQ 並監聽來自 ai-worker 的通知。
    """
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    notification_queue = os.environ.get("RABBITMQ_NOTIFICATION_QUEUE", "notifications_queue")

    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue=notification_queue, durable=True)
            print(' [*] Waiting for notifications. To exit press CTRL+C')

            def callback(ch, method, properties, body):
                print(f" [x] Received notification: {body.decode()}", flush=True)
                try:
                    message = json.loads(body)
                    # 透過 WebSocket 將訊息廣播給所有客戶端
                    # 在真實應用中，你可能會想用 session ID 或 user ID 來指定客戶端
                    print(f" [>] Emitting notification via WebSocket: {message}", flush=True)
                    socketio.emit('notification', message)
                    
                except json.JSONDecodeError:
                    print(" [!] Could not decode message body", flush=True)
                except Exception as e:
                    print(f" [!] Error emitting WebSocket message: {e}", flush=True)
                
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=notification_queue, on_message_callback=callback)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            print(f"Connection to RabbitMQ failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Restarting listener...")
            time.sleep(5)
