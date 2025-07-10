# services/web-app/app/core/minio_service.py

import boto3
from botocore.exceptions import ClientError
from flask import current_app
import uuid

def generate_presigned_upload_url(bucket_name, object_name=None, expiration=3600):
    """
    生成一個預簽章 URL，用於客戶端直接上傳檔案至 MinIO/S3。
    :param bucket_name: 儲存桶名稱
    :param object_name: 在儲存桶中的物件名稱。如果未提供，則生成一個隨機名稱。
    :param expiration: URL 的有效時間（秒）
    :return: 包含 URL 的字典，或在出錯時返回 None
    """
    if object_name is None:
        # 生成一個唯一的檔案名稱，避免衝突
        object_name = f"audio-{uuid.uuid4().hex}.wav"

    s3_client = boto3.client(
        's3',
        endpoint_url=f"http://{current_app.config['MINIO_ENDPOINT']}",
        aws_access_key_id=current_app.config['MINIO_ACCESS_KEY'],
        aws_secret_access_key=current_app.config['MINIO_SECRET_KEY'],
        config=boto3.session.Config(signature_version='s3v4'),
        region_name='us-east-1' # S3 v4 簽章需要一個區域名稱
    )

    try:
        # 確保 bucket 存在
        # 在生產環境中，bucket 應該預先建立好
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                raise

        # 生成預簽章 URL，使用 PUT 方法
        response = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket_name, 'Key': object_name},
            ExpiresIn=expiration,
            HttpMethod='PUT'
        )
    except ClientError as e:
        # 記錄錯誤
        print(f"Error generating presigned URL: {e}")
        return None

    return {'url': response, 'object_name': object_name}
