import unittest
from unittest.mock import Mock, patch

import requests
import guest_activation


class ActivationServiceTests(unittest.TestCase):
    def call_service(self, data=None, status=200, error=None):
        response = Mock(status_code=status)
        response.json.return_value = data
        session = Mock()
        session.get.return_value = response
        session.get.side_effect = error
        with patch.object(guest_activation.requests, 'Session') as factory:
            factory.return_value.__enter__.return_value = session
            result = guest_activation.activate_guest('123', 'secret', 'SG')
        return result, session

    def test_both_reference_success_formats(self):
        for data in ({'status': 'success'}, {'activated': True}):
            with self.subTest(data=data):
                result, session = self.call_service({**data, 'account_id': 456})
                self.assertTrue(result['success'])
                self.assertEqual(result['region'], 'SG')
                self.assertEqual(result['account_id'], 456)
                session.get.assert_called_once_with(
                    guest_activation.ACTIVATION_URL,
                    params={'uid': '123', 'password': 'secret'},
                    headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36'},
                    timeout=10, allow_redirects=False)
                session.post.assert_not_called()

    def test_no_false_success(self):
        for data in ({}, [], {'activated': 'true'}, {'success': True}):
            result, _ = self.call_service(data)
            self.assertFalse(result['success'])

    def test_http_errors_and_redirects(self):
        for status in (302, 429, 503):
            result, session = self.call_service({'status': 'success'}, status)
            self.assertFalse(result['success'])
            self.assertIn(str(status), result['error'])
            self.assertEqual(session.get.call_count, 1)

    def test_errors_do_not_expose_credentials(self):
        for error in (requests.Timeout('password=secret'), requests.ConnectionError('password=secret')):
            result, session = self.call_service(error=error)
            self.assertFalse(result['success'])
            self.assertNotIn('secret', str(result))
            self.assertEqual(session.get.call_count, 1)

    def test_invalid_json(self):
        with patch.object(guest_activation.requests, 'Session') as factory:
            response = factory.return_value.__enter__.return_value.get.return_value
            response.status_code = 200
            response.json.side_effect = ValueError('bad json')
            result = guest_activation.activate_guest('123', 'secret')
        self.assertFalse(result['success'])
        self.assertIn('invalid JSON', result['error'])


if __name__ == '__main__':
    unittest.main()
