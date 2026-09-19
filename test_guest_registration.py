import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from guest_registration import RegistrationGate, RegistrationCooldown


class RegistrationGateTests(unittest.TestCase):
    def test_429_blocks_other_callers_and_respects_retry_after(self):
        gate = RegistrationGate()
        session = Mock()
        session.post.return_value = Mock(status_code=429, headers={'Retry-After': '120'})
        session.post.return_value.json.return_value = {'code': 1006}
        with patch('guest_registration.time.monotonic', return_value=100):
            response = gate.post(session, 'https://example.test')
            self.assertEqual(response.registration_retry_after_seconds, 120)
            with self.assertRaises(RegistrationCooldown) as raised:
                gate.post(session, 'https://example.test')
            self.assertEqual(raised.exception.retry_after_seconds, 120)
            session.post.assert_called_once()

    def test_application_rate_limit_uses_default_cooldown(self):
        gate = RegistrationGate()
        session = Mock()
        session.post.return_value = Mock(status_code=200, headers={})
        session.post.return_value.json.return_value = {'error': 'error_too_many_requests'}
        with patch('guest_registration.time.monotonic', return_value=100):
            self.assertEqual(gate.post(session, 'https://example.test').registration_retry_after_seconds, 60)

    def test_http_date_retry_after_and_cooldown_expiry(self):
        gate = RegistrationGate()
        session = Mock()
        session.post.return_value = Mock(status_code=429, headers={'Retry-After': 'Thu, 01 Jan 1970 00:02:00 GMT'})
        session.post.return_value.json.return_value = {}
        with patch('guest_registration.time.monotonic', return_value=100), patch('guest_registration.time.time', return_value=60):
            self.assertEqual(gate.post(session, 'https://example.test').registration_retry_after_seconds, 60)
        with patch('guest_registration.time.monotonic', return_value=161):
            gate.post(session, 'https://example.test')
        self.assertEqual(session.post.call_count, 2)


class GeneratorCliTests(unittest.TestCase):
    def test_stops_on_429_without_retry(self):
        import guest_generator
        with tempfile.TemporaryDirectory() as directory, patch.object(guest_generator.lssj, 'create_guest_account', return_value={'success': False, 'http_status': 429, 'retry_after_seconds': 60}) as create:
            self.assertEqual(guest_generator.main(['--region', 'SG', '--count', '3', '--output', str(Path(directory)/'accounts.json')]), 1)
            create.assert_called_once()

    def test_partial_credentials_are_saved_before_stopping(self):
        import guest_generator
        result = {'success': False, 'guest_created': True, 'uid': '123', 'password': 'test-secret', 'failed_stage': 'MajorLogin'}
        with tempfile.TemporaryDirectory() as directory, patch.object(guest_generator.lssj, 'create_guest_account', return_value=result):
            path = Path(directory)/'accounts.json'
            self.assertEqual(guest_generator.main(['--region', 'SG', '--output', str(path)]), 1)
            self.assertEqual(json.loads(path.read_text())[0]['password'], 'test-secret')


if __name__ == '__main__':
    unittest.main()
