import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_synthesize_endpoint_exists():
    """
    測試 /api/v1/synthesize 端點是否存在。
    預期會成功，因為我們已經定義了這個路由。
    """
    response = client.post("/api/v1/synthesize", json={"text": "hello"})
    assert response.status_code != 404
    assert response.status_code == 200
