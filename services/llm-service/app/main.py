import os
import pika
import json
import time
from core.llm_service import LLMService

def main():
    # 初始化 LLM 服務
    llm_service = LLMService()

    # 從環境變數讀取 RabbitMQ 設定
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    rpc_queue_name = os.environ.get("RABBITMQ_LLM_QUEUE", "llm_request_queue")

    while True:
        try:
            # 建立 RabbitMQ 連線
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()

            # 宣告 RPC 請求佇列
            channel.queue_declare(queue=rpc_queue_name, durable=True)

            def on_request(ch, method, props, body):
                """處理傳入請求的回呼函式"""
                try:
                    request_data = json.loads(body)
                    text_to_process = request_data.get("text")
                    print(f" [x] 收到請求: {text_to_process}", flush=True)

                    # 使用 LLM 服務產生回應
                    response_text = llm_service.generate_response(text_to_process)
                    response_payload = json.dumps({"message": response_text})

                except json.JSONDecodeError as e:
                    print(f" [!] JSON 解碼錯誤: {e}", flush=True)
                    response_payload = json.dumps({"error": "Invalid JSON format"})
                except Exception as e:
                    print(f" [!] 處理請求時發生錯誤: {e}", flush=True)
                    response_payload = json.dumps({"error": str(e)})

                # 將回應發布到 reply_to 佇列
                ch.basic_publish(
                    exchange='',
                    routing_key=props.reply_to,
                    properties=pika.BasicProperties(correlation_id=props.correlation_id),
                    body=response_payload
                )
                # 確認訊息處理完畢
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f" [✔] 已傳送回應", flush=True)

            # 設定服務品質 (QoS)，確保 worker 一次只處理一個訊息
            channel.basic_qos(prefetch_count=1)
            # 開始從佇列消費訊息
            channel.basic_consume(queue=rpc_queue_name, on_message_callback=on_request)

            print(f" [*] LLM Service 正在等待 RPC 請求於佇列 '{rpc_queue_name}'...", flush=True)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            print(f"與 RabbitMQ 的連線失敗: {e}。5 秒後重試...", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"發生未預期的錯誤: {e}。5 秒後重啟...", flush=True)
            time.sleep(5)

if __name__ == '__main__':
    main()
