import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

# 要測試的模組
from app.core import minio_service

@pytest.fixture
def mock_boto_client(mocker):
    """Fixture to mock the boto3.client."""
    mock_s3 = MagicMock()
    mocker.patch('boto3.client', return_value=mock_s3)
    return mock_s3

def test_generate_presigned_url_success(mock_boto_client, app):
    """
    T-7.1.2: Test successful generation of a presigned URL when the bucket already exists.
    """
    flask_app, _ = app  # 從 app fixture 解構出 Flask app
    bucket_name = "test-bucket"
    object_name = "test-object.wav"
    expected_url = "http://minio.test/signed-url"

    # 模擬 generate_presigned_url 的回傳值
    mock_boto_client.generate_presigned_url.return_value = expected_url

    with flask_app.app_context():
        result = minio_service.generate_presigned_upload_url(bucket_name, object_name)

    # 驗證 head_bucket 被呼叫以檢查 bucket 是否存在
    mock_boto_client.head_bucket.assert_called_once_with(Bucket=bucket_name)
    # 驗證 create_bucket 不應該被呼叫
    mock_boto_client.create_bucket.assert_not_called()
    # 驗證 generate_presigned_url 被正確呼叫
    mock_boto_client.generate_presigned_url.assert_called_once_with(
        'put_object',
        Params={'Bucket': bucket_name, 'Key': object_name},
        ExpiresIn=3600,
        HttpMethod='PUT'
    )
    # 驗證回傳結果
    assert result is not None
    assert result['url'] == expected_url
    assert result['object_name'] == object_name

def test_generate_presigned_url_bucket_creation(mock_boto_client, app):
    """
    T-7.1.2: Test successful URL generation when the bucket does not exist and is created.
    """
    flask_app, _ = app  # 從 app fixture 解構出 Flask app
    bucket_name = "new-bucket"
    object_name = "new-object.wav"
    expected_url = "http://minio.test/new-signed-url"

    # 模擬 head_bucket 拋出 404 錯誤
    mock_boto_client.head_bucket.side_effect = ClientError(
        {'Error': {'Code': '404', 'Message': 'Not Found'}},
        'HeadBucket'
    )
    mock_boto_client.generate_presigned_url.return_value = expected_url

    with flask_app.app_context():
        result = minio_service.generate_presigned_upload_url(bucket_name, object_name)

    # 驗證 head_bucket 被呼叫
    mock_boto_client.head_bucket.assert_called_once_with(Bucket=bucket_name)
    # 驗證 create_bucket 因為 bucket 不存在而被呼叫
    mock_boto_client.create_bucket.assert_called_once_with(Bucket=bucket_name)
    # 驗證 URL 仍然成功生成
    mock_boto_client.generate_presigned_url.assert_called_once()
    assert result is not None
    assert result['url'] == expected_url

def test_generate_presigned_url_client_error_on_generate(mock_boto_client, app):
    """
    T-7.1.2: Test that the function returns None if ClientError occurs during URL generation.
    """
    flask_app, _ = app  # 從 app fixture 解構出 Flask app
    bucket_name = "test-bucket"
    object_name = "test-object.wav"

    # 模擬 generate_presigned_url 拋出 ClientError
    mock_boto_client.generate_presigned_url.side_effect = ClientError(
        {'Error': {'Code': '500', 'Message': 'Internal Server Error'}},
        'GeneratePresignedUrl'
    )

    with flask_app.app_context():
        result = minio_service.generate_presigned_upload_url(bucket_name, object_name)

    # 驗證函式捕獲異常並返回 None
    assert result is None

def test_generate_presigned_url_head_bucket_error_raises(mock_boto_client, app):
    """
    T-7.1.2: Test that non-404 ClientError from head_bucket is re-raised.
    """
    flask_app, _ = app  # 從 app fixture 解構出 Flask app
    bucket_name = "test-bucket"
    object_name = "test-object.wav"

    # 模擬 head_bucket 拋出一個非 404 的 ClientError
    error_response = {'Error': {'Code': '503', 'Message': 'Service Unavailable'}}
    mock_boto_client.head_bucket.side_effect = ClientError(error_response, 'HeadBucket')

    with flask_app.app_context():
        # 驗證此錯誤會被向上拋出，而不是被內部處理
        with pytest.raises(ClientError) as excinfo:
            minio_service.generate_presigned_upload_url(bucket_name, object_name)

    # 驗證拋出的就是我們模擬的那個錯誤
    assert excinfo.value.response['Error']['Code'] == '503'
    # 驗證 create_bucket 和 generate_presigned_url 都沒有被呼叫
    mock_boto_client.create_bucket.assert_not_called()
    mock_boto_client.generate_presigned_url.assert_not_called()