# services/web-app/tests/test_line_service.py
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from app.core.line_service import LineService

class TestLineService(unittest.TestCase):

    def setUp(self):
        """Set up a test Flask app and a LineService instance."""
        self.app = Flask(__name__)
        self.app.config['LINE_CHANNEL_SECRET'] = 'test_secret'
        self.app.config['LINE_CHANNEL_ACCESS_TOKEN'] = 'test_token'
        self.app.config['LINE_RICH_MENU_ID_MEMBER'] = 'member_menu_id'

        # Mock external services that LineService depends on
        self.user_repo_mock = MagicMock()
        self.chat_repo_mock = MagicMock()
        self.rabbitmq_service_mock = MagicMock()
        self.minio_service_mock = MagicMock()
        self.line_api_mock = MagicMock()

        # Use patch to replace the actual services with mocks
        self.patchers = [
            patch('app.core.line_service.UserRepository', return_value=self.user_repo_mock),
            patch('app.core.line_service.ChatRepository', return_value=self.chat_repo_mock),
            patch('app.core.line_service.get_rabbitmq_service', return_value=self.rabbitmq_service_mock),
            patch('app.core.line_service.get_minio_service', return_value=self.minio_service_mock),
            patch('app.core.line_service.ApiClient', return_value=MagicMock().__enter__.return_value),
            patch('app.core.line_service.MessagingApi', return_value=self.line_api_mock),
            patch('app.core.line_service.MessagingApiBlob', return_value=MagicMock())
        ]
        for p in self.patchers:
            p.start()

        self.line_service = LineService(
            channel_secret='test_secret',
            channel_access_token='test_token'
        )

    def tearDown(self):
        """Stop all patchers."""
        for p in self.patchers:
            p.stop()


if __name__ == '__main__':
    unittest.main()
