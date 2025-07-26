import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
from app.main import app
from app.dependencies import get_service # 從新的依賴檔案匯入

client = TestClient(app)

# 建立一個可重複使用的 Mock LLM Service
@pytest.fixture
def mock_llm_service():
    # 建立一個 Mock 物件，並定義 generate_response 方法
    service = Mock()
    service.generate_response.return_value = "Mocked response"
    return service

def test_chat_calls_llm_service(mock_llm_service):
    """
    測試 /api/v1/chat 端點是否會呼叫 LLMService。
    我們使用 dependency_overrides 來注入一個 mock service。
    """
    # 使用 FastAPI 的依賴覆蓋功能
    app.dependency_overrides[get_service] = lambda: mock_llm_service
    
    # 發送請求
    response = client.post("/api/v1/chat", json={"text": "test message"})
    
    # 斷言 Mock Service 的方法被呼叫了一次，且參數正確
    mock_llm_service.generate_response.assert_called_once_with("test message")
    
    # 斷言 API 回應是 Mock Service 回傳的值
    assert response.json() == {"message": "Mocked response"}
    
    # 清理依賴覆蓋，避免影響其他測試
    app.dependency_overrides.clear()

def test_chat_endpoint_exists():
    """
    測試 /api/v1/chat 端點是否存在。
    """
    response = client.post("/api/v1/chat", json={"text": "hello"})
    assert response.status_code != 404
    assert response.status_code == 200
    # 驗證真實服務的回應
    assert "Echo: hello" in response.text

def test_chat_requires_text_field():
    """
    測試 /api/v1/chat 端點在缺少 'text' 欄位時是否會回傳 422。
    """
    response = client.post("/api/v1/chat", json={"irrelevant_field": "some_value"})
    assert response.status_code == 422


