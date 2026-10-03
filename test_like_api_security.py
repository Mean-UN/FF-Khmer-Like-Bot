import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import lssj


class LikeApiSecurityTests(unittest.TestCase):
    def test_unauthorized_requests_do_no_work(self):
        client = lssj.app.test_client()
        with patch.dict(os.environ, {'LIKE_API_KEY': 'test-secret'}), patch.object(lssj, 'get_cached_region') as lookup, patch.object(lssj, 'load_like_tokens') as tokens, patch.object(lssj, 'send_like_requests') as send:
            for endpoint in ('like', 'likeff'):
                for headers in ({}, {'X-API-Key': 'wrong'}, {'X-API-Key': '\u00e9'}):
                    response = client.get(f'/{endpoint}?uid=123&password=test-secret', headers=headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.json['code'], 'LIKE_API_UNAUTHORIZED')
            lookup.assert_not_called()
            tokens.assert_not_called()
            send.assert_not_called()

    def test_correct_key_reaches_input_validation(self):
        with patch.dict(os.environ, {'LIKE_API_KEY': 'test-secret'}):
            for endpoint in ('like', 'likeff'):
                response = lssj.app.test_client().get('/' + endpoint, headers={'X-API-Key': 'test-secret'})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error'], 'UID is required. Use /' + endpoint + '?uid=xxx')

    def test_missing_configuration_fails_closed(self):
        with patch.dict(os.environ, {'LIKE_API_KEY': ''}):
            for endpoint in ('like', 'likeff'):
                self.assertEqual(lssj.app.test_client().get('/' + endpoint).status_code, 503)

    def test_bot_sends_key_only_to_like_endpoints(self):
        source = ast.parse(Path('telegram_bot.py').read_text(encoding='utf-8'))
        function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'call_api')
        requests = SimpleNamespace(get=Mock(return_value=Mock(status_code=200, json=Mock(return_value={'success': True}))), Timeout=TimeoutError, RequestException=Exception)
        namespace = {'os': os, 'requests': requests, 'API_BASE_URL': 'https://example.test'}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'telegram_bot.py', 'exec'), namespace)
        with patch.dict(os.environ, {'LIKE_API_KEY': 'test-secret'}):
            for endpoint in ('like', '/likeff'):
                namespace['call_api'](endpoint, {'uid': '123'})
                self.assertEqual(requests.get.call_args.kwargs['headers'], {'X-API-Key': 'test-secret'})
                self.assertFalse(requests.get.call_args.kwargs['allow_redirects'])
            namespace['call_api']('jwt', {})
            self.assertNotIn('headers', requests.get.call_args.kwargs)
        requests.get.reset_mock()
        with patch.dict(os.environ, {'LIKE_API_KEY': ''}):
            self.assertFalse(namespace['call_api']('like', {})['success'])
            requests.get.assert_not_called()
