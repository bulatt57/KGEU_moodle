import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
from main import (
    load_user_data,
    save_user_data,
    get_final_url,
    JSON_FILE
)

class TestMoodleBotFunctions(unittest.TestCase):
    def setUp(self):
        # Create a temporary JSON file for testing
        self.test_json_file = 'test_user_data.json'
        self.test_data = {
            "123": {
                "username": "test_user",
                "password": "test_pass"
            }
        }
        
    def tearDown(self):
        # Clean up any test files
        if os.path.exists(self.test_json_file):
            os.remove(self.test_json_file)

    def test_load_user_data_file_not_found(self):
        """Test loading user data when file doesn't exist"""
        with patch('main.JSON_FILE', self.test_json_file):
            data = load_user_data()
            self.assertEqual(data, {})

    def test_load_and_save_user_data(self):
        """Test saving and loading user data"""
        with patch('main.JSON_FILE', self.test_json_file):
            # Save test data
            save_user_data(self.test_data)
            
            # Load and verify data
            loaded_data = load_user_data()
            self.assertEqual(loaded_data, self.test_data)

    def test_get_final_url(self):
        """Test get_final_url function with mock session"""
        mock_session = Mock()
        initial_url = "http://test.com/redirect"
        final_url = "http://test.com/final"
        
        # Mock the response with a history to simulate redirects
        mock_response = Mock()
        mock_response.url = final_url
        mock_session.get.return_value = mock_response
        
        result = get_final_url(mock_session, initial_url)
        self.assertEqual(result, final_url)
        mock_session.get.assert_called_once_with(initial_url, allow_redirects=True)

    @patch('requests.Session')
    def test_login_flow(self, mock_session):
        """Test the login process with mock responses"""
        mock_response = Mock()
        mock_response.text = "<input name='logintoken' value='test_token'>"
        mock_session.return_value.get.return_value = mock_response
        
        # Test will be expanded based on login flow implementation

class TestAsyncFunctions(unittest.IsolatedAsyncioTestCase):
    async def test_send_welcome(self):
        """Test the welcome message handler"""
        # This would test the send_welcome function
        # Implementation will use aiogram's TestClient
        pass

    async def test_handle_my_courses(self):
        """Test the my courses handler"""
        # This would test the handle_my_courses function
        # Implementation will use aiogram's TestClient
        pass

if __name__ == '__main__':
    unittest.main() 