import pytest
from unittest.mock import MagicMock, patch
import pika
from pika.exceptions import AMQPConnectionError

# 要測試的模組
from app.core.rabbitmq_service import RabbitMQService, get_rabbitmq_service

@pytest.fixture
def mock_pika(mocker):
    """Fixture to mock the entire pika library."""
    return mocker.patch('app.core.rabbitmq_service.pika')

def test_publish_message_success(mock_pika):
    """
    T-7.1.3: Test successful message publishing.
    """
    # 準備 mock 物件
    mock_connection = MagicMock()
    mock_channel = MagicMock()
    mock_pika.URLParameters.return_value = "mock_params"
    mock_pika.BlockingConnection.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel

    # 建立服務實例並呼叫方法
    service = RabbitMQService("amqp://test")
    service.publish_message("test_queue", {"key": "value"})

    # 驗證 pika 的函式被正確呼叫
    mock_pika.BlockingConnection.assert_called_once_with("mock_params")
    mock_connection.channel.assert_called_once()
    mock_channel.queue_declare.assert_called_once_with(queue="test_queue", durable=True)
    mock_channel.basic_publish.assert_called_once()
    
    # 驗證訊息內容
    args, kwargs = mock_channel.basic_publish.call_args
    assert kwargs['exchange'] == ''
    assert kwargs['routing_key'] == 'test_queue'
    assert kwargs['body'] == '{"key": "value"}'
    
    # 驗證連線最後被關閉
    mock_connection.close.assert_called_once()

def test_publish_message_connection_error(mock_pika):
    """
    T-7.1.3: Test that an exception is raised on connection failure.
    """
    # 模擬連線失敗
    mock_pika.BlockingConnection.side_effect = AMQPConnectionError("Connection failed")

    service = RabbitMQService("amqp://fail")

    # 驗證呼叫 publish_message 時會拋出 AMQPConnectionError
    with pytest.raises(AMQPConnectionError):
        service.publish_message("test_queue", {"key": "value"})

    # 驗證 channel 和 publish 都沒有被呼叫
    assert not hasattr(service, 'channel') or service.channel is None


def test_publish_message_ensures_connection_closed_on_error(mock_pika):
    """
    T-7.1.3: Test that the connection is closed even if publishing fails.
    """
    # 準備 mock 物件
    mock_connection = MagicMock()
    mock_channel = MagicMock()
    mock_pika.BlockingConnection.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel

    # 模擬 basic_publish 拋出異常
    mock_channel.basic_publish.side_effect = Exception("Publishing failed")

    service = RabbitMQService("amqp://test")

    # 驗證呼叫時會拋出異常
    with pytest.raises(Exception, match="Publishing failed"):
        service.publish_message("test_queue", {"key": "value"})

    # 最重要的驗證：即使發生錯誤，連線關閉的函式依然被呼叫
    mock_connection.close.assert_called_once()

def test_get_rabbitmq_service_returns_instance():
    """
    Tests that the dependency injector function returns the correct service instance.
    """
    service_instance = get_rabbitmq_service()
    assert isinstance(service_instance, RabbitMQService)
