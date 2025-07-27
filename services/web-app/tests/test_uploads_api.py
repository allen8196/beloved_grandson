import pytest
from unittest.mock import patch

def test_request_upload_url_success(client):
    """
    T-7.1.4: Test successful request for an upload URL.
    """
    mock_result = {"url": "http://mock-url.com", "object_name": "generated-name.wav"}
    
    with patch('app.api.uploads.minio_service.generate_presigned_upload_url', return_value=mock_result) as mock_generate:
        response = client.post('/audio/request-url', json={})
        
        assert response.status_code == 200
        assert response.json == mock_result
        mock_generate.assert_called_once_with(bucket_name='audio-uploads', object_name=None)

def test_request_upload_url_with_filename(client):
    """
    T-7.1.4: Test successful request specifying a filename.
    """
    mock_result = {"url": "http://mock-url.com", "object_name": "custom-name.wav"}
    
    with patch('app.api.uploads.minio_service.generate_presigned_upload_url', return_value=mock_result) as mock_generate:
        response = client.post('/audio/request-url', json={"filename": "custom-name.wav"})
        
        assert response.status_code == 200
        assert response.json == mock_result
        mock_generate.assert_called_once_with(bucket_name='audio-uploads', object_name="custom-name.wav")

def test_request_upload_url_minio_failure(client):
    """
    T-7.1.4: Test API's response when the minio_service fails.
    """
    with patch('app.api.uploads.minio_service.generate_presigned_upload_url', return_value=None) as mock_generate:
        response = client.post('/audio/request-url', json={})
        
        assert response.status_code == 500
        assert response.json == {"error": "Could not generate presigned URL"}
        mock_generate.assert_called_once()

@pytest.mark.xfail(reason="Authentication has not been implemented on this endpoint yet.")
def test_request_upload_url_requires_auth(client):
    """
    T-7.1.4: Mark as xfail until authentication is added.
    This test should fail now but is expected to pass in the future.
    """
    response = client.post('/audio/request-url', json={})
    # Once auth is implemented, we expect a 401 or 403 error without a valid token
    assert response.status_code in [401, 403]
