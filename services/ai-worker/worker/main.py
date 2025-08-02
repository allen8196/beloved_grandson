import os
import pika
import json
import time
import uuid

def publish_notification(message: dict, patient_id: int):
    """將訊息發佈到通知佇列。"""
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    notification_queue = os.environ.get("RABBITMQ_NOTIFICATION_QUEUE", "notifications_queue")
    try:
        message_with_id = message.copy()
        message_with_id['patient_id'] = patient_id
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
        channel = connection.channel()
        channel.queue_declare(queue=notification_queue, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=notification_queue,
            body=json.dumps(message_with_id),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        print(f"已發送通知: {message_with_id}", flush=True)
        connection.close()
    except pika.exceptions.AMQPConnectionError as e:
        print(f"連線到 RabbitMQ 以發送通知時出錯: {e}", flush=True)
        raise

class BaseRpcClient:
    """RPC 客戶端的基底類別。"""
    def __init__(self, rpc_queue_name: str):
        self.rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
        self.rpc_queue = rpc_queue_name
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
        """處理回應訊息。"""
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, payload: dict, timeout: int = 30):
        """發送 RPC 請求並等待回應。"""
        self.response = None
        self.corr_id = str(uuid.uuid4())

        self.channel.basic_publish(
            exchange='',
            routing_key=self.rpc_queue,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=json.dumps(payload)
        )
        print(f" [x] 已發送 RPC 請求到 {self.rpc_queue}: {payload}", flush=True)

        self.connection.process_data_events(time_limit=timeout)

        if self.response is None:
            raise TimeoutError(f"{self.rpc_queue} 服務 RPC 請求超時")

        return json.loads(self.response)

    def close(self):
        if self.connection.is_open:
            self.connection.close()
            print(f"{self.rpc_queue} RPC 客戶端連線已關閉。", flush=True)

class SttRpcClient(BaseRpcClient):
    def __init__(self):
        super().__init__(os.environ.get("RABBITMQ_STT_QUEUE", "stt_request_queue"))

class LlmRpcClient(BaseRpcClient):
    def __init__(self):
        super().__init__(os.environ.get("RABBITMQ_LLM_QUEUE", "llm_request_queue"))

class TtsRpcClient(BaseRpcClient):
    def __init__(self):
        super().__init__(os.environ.get("RABBITMQ_TTS_QUEUE", "tts_request_queue"))


def process_text_task(text_message: str):
    """透過 RabbitMQ RPC 呼叫 llm-service 來處理文字訊息。"""
    llm_rpc_client = None
    try:
        print("建立 LLM RPC 客戶端...", flush=True)
        llm_rpc_client = LlmRpcClient()
        response = llm_rpc_client.call({"text": text_message})
        print(f"成功呼叫 LLM 服務。回應: {response}", flush=True)
        return response
    finally:
        if llm_rpc_client:
            llm_rpc_client.close()

def process_audio_task(patient_id: int, bucket_name: str, object_name: str, audio_duration_ms=60000):
    """
    透過 STT -> LLM -> TTS 管道處理音訊檔案任務。
    """
    stt_client, llm_client, tts_client = None, None, None
    try:
        # 步驟 1: STT - 語音轉文字
        print(f"--- 開始 STT 處理: {object_name} ---", flush=True)
        stt_client = SttRpcClient()
        stt_response = stt_client.call({"bucket_name": bucket_name, "object_name": object_name})
        user_transcript = stt_response.get("transcribed_text")
        if not user_transcript:
            raise ValueError("STT 服務未返回有效的轉錄文字")
        print(f"STT 結果: {user_transcript}", flush=True)


        ai_response = 'aaaa'
        # 步驟 2: LLM - 產生 AI 回應
        # print(f"--- 開始 LLM 處理 ---", flush=True)
        # llm_client = LlmRpcClient()
        # llm_response = llm_client.call({"text": user_transcript})
        # ai_response = llm_response.get("message")
        # if not ai_response:
        #     raise ValueError("LLM 服務未返回有效的 AI 回應")
        # print(f"LLM 結果: {ai_response}", flush=True)

        # 步驟 3: TTS - 文字轉語音
        print(f"--- 開始 TTS 處理 ---", flush=True)
        tts_client = TtsRpcClient()
        tts_response = tts_client.call({"text": ai_response})
        response_audio_url = tts_response.get("object_name") # TODO tts_response 回應檔案錯誤
        print(dict(tts_response), '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        if not response_audio_url:
            raise ValueError("TTS 服務未返回有效的音訊物件名稱")
        print(f"TTS 結果: {response_audio_url}", flush=True)

        # 步驟 4: 發送成功通知
        notification_message = {
            "status": "completed",
            "original_file": object_name,
            "user_transcript": user_transcript,
            "ai_response": ai_response,
            "response_audio_url": response_audio_url,
            "audio_duration_ms": audio_duration_ms # TODO 秒數要改
        }
        publish_notification(notification_message, patient_id)

    except Exception as e:
        print(f"音訊處理管道中發生錯誤: {e}", flush=True)
        error_notification = {
            "status": "error",
            "original_file": object_name,
            "error_message": str(e)
        }
        publish_notification(error_notification, patient_id)
        raise
    finally:
        # 確保所有客戶端連線都被關閉
        if stt_client:
            stt_client.close()
        # if llm_client:
        #     llm_client.close()
        if tts_client:
            tts_client.close()


if __name__ == '__main__':
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    task_queue = os.environ.get("RABBITMQ_QUEUE", "task_queue")

    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue=task_queue, durable=True)
            print(' [*] AI Worker 正在等待訊息。按 CTRL+C 離開', flush=True)

            def callback(ch, method, properties, body):
                task_data = json.loads(body)
                print(f"\n [x] 收到任務: {task_data}", flush=True)
                try:
                    patient_id = task_data.get('patient_id')
                    if not patient_id:
                        raise ValueError("任務資料缺少 'patient_id'")

                    if 'text' in task_data:
                        print(f" [*] 開始為病患 {patient_id} 處理文字任務...", flush=True)
                        llm_response = process_text_task(task_data['text'])
                        notification = {
                            "status": "completed",
                            "user_transcript": task_data['text'],
                            "ai_response": llm_response.get("message", "")
                        }
                        publish_notification(notification, patient_id)
                    elif 'bucket_name' in task_data and 'object_name' in task_data:
                        audio_duration_ms = task_data.get('duration_ms')
                        print(f" [*] 開始為病患 {patient_id} 處理音訊任務...", flush=True)
                        process_audio_task(patient_id, task_data['bucket_name'], task_data['object_name'], audio_duration_ms)
                    else:
                        print(f" [!] 未知的任務格式: {task_data}", flush=True)
                    print(f" [✔] 任務成功完成。", flush=True)
                except Exception as e:
                    print(f" [!] 處理任務時出錯: {e}", flush=True)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_consume(queue=task_queue, on_message_callback=callback)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            print(f"與 RabbitMQ 的連線失敗: {e}。5 秒後重試...", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"發生未預期的錯誤: {e}。正在重啟消費者...", flush=True)
            time.sleep(5)
