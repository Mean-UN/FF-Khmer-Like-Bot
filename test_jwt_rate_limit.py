import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from jwt_rate_limit import JwtRateLimit


class JwtRateLimitTests(unittest.TestCase):
    def test_wait_rechecks_quota_without_long_sleeps(self):
        limiter = JwtRateLimit('unused')
        with patch.object(limiter, 'reserve', side_effect=[60, 1, 0]) as reserve, patch('jwt_rate_limit.time.sleep') as sleep:
            limiter.wait()
            self.assertEqual(reserve.call_count, 3)
            self.assertEqual([call.args for call in sleep.call_args_list], [(1,), (1,)])

    def test_refresh_reserves_before_authentication_and_on_retry(self):
        import lssj
        events = []
        def authenticate(*args):
            events.append('auth')
            raise ValueError('mock login failure')
        with patch.object(lssj.token_refresh_rate_limit, 'wait', side_effect=lambda: events.append('reserve')), patch.object(lssj.jwt_protocol, 'generate_access_token', side_effect=authenticate), patch.object(lssj.time, 'sleep'):
            with self.assertRaises(ValueError):
                lssj.fetch_guest_jwt_for_like_with_retry('123', 'fake', max_retries=2)
        self.assertEqual(events, ['reserve', 'auth', 'reserve', 'auth'])

    def test_sliding_window_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'quota.sqlite3')
            limiter = JwtRateLimit(path)
            with patch('jwt_rate_limit.time.time', return_value=1000):
                self.assertEqual([limiter.reserve() for _ in range(100)], [0] * 100)
                self.assertEqual(JwtRateLimit(path).reserve(), 60)
            with patch('jwt_rate_limit.time.time', return_value=1059.1):
                self.assertEqual(limiter.reserve(), 1)
            with patch('jwt_rate_limit.time.time', return_value=1060):
                self.assertEqual(limiter.reserve(), 0)

    def test_concurrent_workers_share_quota(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'quota.sqlite3')
            with patch('jwt_rate_limit.time.time', return_value=1000):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(lambda _: JwtRateLimit(path).reserve(), range(120)))
            self.assertEqual(results.count(0), 100)
            self.assertEqual(results.count(60), 20)

    def test_route_rejects_before_authentication(self):
        import lssj
        client = lssj.app.test_client()
        with patch.object(lssj.jwt_rate_limit, 'reserve', return_value=12), patch.object(lssj.jwt_protocol, 'generate_access_token') as auth, patch.object(lssj.jwt_protocol, 'inspect_token') as inspect:
            for response in (client.get('/jwt?uid=123&pw=pw'),
                             client.post('/jwt', json={'access_token': 'access'})):
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response.headers['Retry-After'], '12')
                self.assertEqual(response.json['retry_after'], 12)
            self.assertEqual(client.get('/jwt').status_code, 400)
            auth.assert_not_called()
            inspect.assert_not_called()
