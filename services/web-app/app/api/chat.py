import os
from flask import Blueprint, request, jsonify
from app.core.rabbitmq_service import get_rabbitmq_service
from app.core import minio_service
from werkzeug.exceptions import BadRequest

bp = Blueprint('chat', __name__, url_prefix='/api/v1/chat')

@bp.route('/text', methods=['POST'])
def post_text_message():
    """
    Receives a text message and publishes it to the AI worker queue.
    ---
    tags:
      - chat
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            patient_id:
              type: string
              description: The ID of the patient sending the message.
            text:
              type: string
              description: The text content of the message.
    responses:
      202:
        description: Message received and queued for processing.
      400:
        description: Invalid input, missing required fields.
      500:
        description: Failed to publish message to the queue.
    """
    try:
        data = request.get_json()
        if not data or 'patient_id' not in data or 'text' not in data:
            raise BadRequest("Missing 'patient_id' or 'text' in request body.")
        
        patient_id = data['patient_id']
        text = data['text']
        
        message_body = {
            'patient_id': patient_id,
            'text': text
        }
        
        rabbitmq_service = get_rabbitmq_service()
        task_queue_name = os.environ.get("RABBITMQ_QUEUE", "task_queue")
        print(f"[*] Publishing task to {task_queue_name}: {message_body}", flush=True)
        rabbitmq_service.publish_message(
            queue_name=task_queue_name,
            message_body=message_body
        )
        
        return jsonify({"status": "accepted", "message": "Message received and queued for processing."}), 202

    except BadRequest as e:
        return jsonify({"error": {"code": "INVALID_INPUT", "message": str(e)}}), 400
    except Exception as e:
        return jsonify({"error": {"code": "QUEUE_PUBLISH_ERROR", "message": f"Failed to publish message to queue: {e}"}}), 500

@bp.route('/audio', methods=['POST'])
def post_audio_message():
    """
    Handles audio message submissions and triggers the processing pipeline.
    This endpoint receives a patient ID and a filename, then publishes a
    task to the AI worker for asynchronous processing. It's the starting
    point for the entire speech-to-text and analysis workflow.
    ---
    tags:
      - chat
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            patient_id:
              type: string
              description: The ID of the patient associated with the audio.
              example: "patient_123"
            filename:
              type: string
              description: The exact name of the audio file previously uploaded to MinIO.
              example: "Anya_music.mp3"
    responses:
      202:
        description: Task accepted for processing. The response includes the data sent to the queue.
        schema:
          type: object
          properties:
            status:
              type: string
              example: "accepted"
            data:
              type: object
              properties:
                patient_id:
                  type: string
                object_name:
                  type: string
                bucket_name:
                  type: string
      400:
        description: Invalid input, missing required fields.
      500:
        description: Internal server error, e.g., failed to publish to the queue.
    """
    try:
        data = request.get_json()
        if not data or 'patient_id' not in data or 'filename' not in data:
            raise BadRequest("Missing 'patient_id' or 'filename' in request body.")
            
        patient_id = data.get('patient_id')
        filename = data.get('filename')

        # For simplicity in the current workflow, we directly use the provided filename
        # and assume it's in the correct bucket. The presigned URL generation logic
        # is maintained but its output is not returned to the client in this flow.
        bucket_name = 'audio-uploads'
        object_name = filename

        # Publish a task to RabbitMQ
        message_body = {
            'patient_id': patient_id,
            'object_name': object_name,
            'bucket_name': bucket_name
        }
        rabbitmq_service = get_rabbitmq_service()
        task_queue_name = os.environ.get("RABBITMQ_QUEUE", "task_queue")
        rabbitmq_service.publish_message(
            queue_name=task_queue_name,
            message_body=message_body
        )

        # Return a confirmation response
        return jsonify({"status": "accepted", "data": message_body}), 202

    except BadRequest as e:
        return jsonify({"error": {"code": "INVALID_INPUT", "message": str(e)}}), 400
    except Exception as e:
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}}), 500
