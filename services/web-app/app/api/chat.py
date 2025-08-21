import os
from flask import Blueprint, request, jsonify, abort
from app.core.chat_repository import ChatRepository
from app.core.user_repository import UserRepository
from app.core.rabbitmq_service import get_rabbitmq_service
from werkzeug.exceptions import BadRequest, NotFound

import logging

bp = Blueprint('chat', __name__, url_prefix='/api/v1')

@bp.route('/chat/text', methods=['POST'])
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

@bp.route('/chat/audio', methods=['POST'])
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

@bp.route('/patients/<int:patient_id>/conversations', methods=['GET'])
def get_conversations(patient_id):
    """
    Retrieves a list of conversations for a specific patient.
    ---
    tags:
      - chat
    parameters:
      - in: path
        name: patient_id
        type: integer
        required: true
        description: The ID of the patient to retrieve conversations for.
    responses:
      200:
        description: A list of conversations.
        schema:
          type: array
          items:
            type: object
            properties:
              _id:
                type: string
              patient_id:
                type: integer
              start_time:
                type: string
                format: date-time
      404:
        description: Patient not found.
      500:
        description: Internal server error.
    """
    try:
        user_repo = UserRepository()
        patient = user_repo.find_by_id(patient_id)
        if not patient or patient.is_staff:
            raise NotFound("Patient not found.")
            
        chat_repo = ChatRepository()
        conversations = chat_repo.get_conversations_by_patient_id(patient_id=patient_id)
        return jsonify(conversations)
    except NotFound as e:
        return jsonify({"error": {"code": "NOT_FOUND", "message": str(e)}}), 404
    except Exception as e:
        logging.error(f"Error getting conversations for patient {patient_id}: {e}", exc_info=True)
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred."}}), 500

@bp.route('/conversations/<string:conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    """
    Retrieves all messages for a specific conversation.
    ---
    tags:
      - chat
    parameters:
      - in: path
        name: conversation_id
        type: string
        required: true
        description: The ID of the conversation to retrieve messages for.
    responses:
      200:
        description: A list of messages.
        schema:
          type: array
          items:
            type: object
            properties:
              _id:
                type: string
              conversation_id:
                type: string
              sender_type:
                type: string
              content:
                type: string
              timestamp:
                type: string
                format: date-time
      404:
        description: Conversation not found.
      500:
        description: Internal server error.
    """
    try:
        chat_repo = ChatRepository()
        
        conversation = chat_repo.find_conversation_by_id(conversation_id)
        if not conversation:
            raise NotFound("Conversation not found.")
            
        messages = chat_repo.get_messages_by_conversation_id(conversation_id=conversation_id)
        return jsonify(messages)
    except NotFound as e:
        return jsonify({"error": {"code": "NOT_FOUND", "message": str(e)}}), 404
    except Exception as e:
        logging.error(f"Error getting messages for conversation {conversation_id}: {e}", exc_info=True)
        return jsonify({"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred."}}), 500

from app.core.line_service import get_line_service
from linebot.v3.exceptions import InvalidSignatureError

@bp.route('/chat/webhook', methods=['POST'])
def line_webhook():
    """
    Webhook endpoint for receiving events from the LINE Platform.
    This is the single entry point for all user interactions from LINE.
    ---
    tags:
      - chat
      - line
    parameters:
      - in: header
        name: X-Line-Signature
        type: string
        required: true
        description: Signature for verifying the request origin.
      - in: body
        name: body
        required: true
        description: The request body contains the list of webhook events.
        schema:
          type: object
    responses:
      200:
        description: Successfully processed the event(s).
      400:
        description: Invalid request, e.g., missing signature or bad request body.
    """
    
    # Get X-Line-Signature header value
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        abort(400, "X-Line-Signature header is required.")

    # Get request body as text
    body = request.get_data(as_text=True)
    
    line_service = get_line_service()
    try:
        line_service.handle_webhook(body, signature)
    except InvalidSignatureError:
        logging.warning("Invalid signature received for LINE webhook.")
        abort(400, "Invalid signature.")
    except Exception as e:
        logging.error(f"Error processing LINE webhook: {e}", exc_info=True)
        # Return OK to LINE platform even if internal error occurs
        # to prevent retries for a message that is already causing an error.
        return 'OK'

    return 'OK'
