"""Offline checks for the supplied OB55 like request protocol."""
import unittest
from unittest.mock import AsyncMock, Mock, patch
import lssj


class LikeProtocolTests(unittest.IsolatedAsyncioTestCase):
    def test_headers_and_regions(self):
        for token in ('example-token', 'Bearer example-token'):
            headers = lssj.like_headers(token)
            self.assertEqual(headers['Authorization'], 'Bearer example-token')
            self.assertEqual(headers['ReleaseVersion'], lssj.jwt_protocol.RELEASE_VERSION)
            self.assertIn('UnityPlayer/2018.4.12f1', headers['User-Agent'])
            self.assertEqual(headers['X-Unity-Version'], '2018.4.12f1')
        for region in ('BR', 'US', 'SAC', 'NA'):
            self.assertEqual(lssj.like_server_url(region), 'https://client.us.freefiremobile.com')
        self.assertEqual(lssj.like_server_url('ind'), 'https://client.ind.freefiremobile.com')
        self.assertEqual(lssj.like_server_url('BD'), 'https://clientbp.ppmainecoonghj.com')

    async def test_saved_tokens_send_without_legacy_login(self):
        with patch.object(lssj, 'RtY', new_callable=AsyncMock) as login, patch.object(lssj, 'send_like_request', new_callable=AsyncMock, return_value=200) as send:
            self.assertEqual(await lssj.send_like_requests('123', 'BR', tokens=['one', 'two']), [200, 200])
            login.assert_not_awaited()
            self.assertEqual(send.await_args_list[0].args[2], 'https://client.us.freefiremobile.com/LikeProfile')

    async def test_saved_token_reads_without_legacy_login(self):
        client = AsyncMock()
        client.post.return_value = Mock(content=lssj.like_count_pb2.Info().SerializeToString())
        with patch.object(lssj, 'RtY', new_callable=AsyncMock) as login, patch.object(lssj.httpx, 'AsyncClient') as factory:
            factory.return_value.__aenter__.return_value = client
            await lssj.fetch_like_info('123', 'IND', 'example-token')
            login.assert_not_awaited()
            self.assertEqual(client.post.await_args.args[0], 'https://client.ind.freefiremobile.com/GetPlayerPersonalShow')
            self.assertEqual(client.post.await_args.kwargs['headers']['Authorization'], 'Bearer example-token')

    async def test_missing_tokens_retain_login_fallback(self):
        with patch.object(lssj, 'RtY', new_callable=AsyncMock, return_value=('fallback', 'BD', 'unused')) as login, patch.object(lssj, 'send_like_request', new_callable=AsyncMock, return_value=200):
            self.assertEqual(await lssj.send_like_requests('123', 'BD'), [200])
            login.assert_awaited_once_with('BD')


class LikeBatchDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_220_tokens_sent_with_bounded_concurrency_and_shared_client(self):
        import asyncio
        active = 0
        peak = 0
        clients = set()
        received = []
        async def send(payload, token, url, client=None):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            clients.add(id(client))
            received.append(token)
            await asyncio.sleep(0)
            active -= 1
            return 200
        tokens = ['token-' + str(n) for n in range(220)]
        with patch.object(lssj, 'send_like_request', side_effect=send):
            results = await lssj.send_like_requests('123', 'SG', tokens=tokens)
        self.assertEqual(len(results), 220)
        self.assertEqual(set(received), set(tokens))
        self.assertLessEqual(peak, 25)
        self.assertEqual(len(clients), 1)

    def test_results_distinguish_rejections_and_network_failures(self):
        result = lssj.summarize_like_results([200, 200, 401, 429, 'ReadTimeout', RuntimeError('private details')])
        self.assertEqual(result['attempted'], 6)
        self.assertEqual(result['http_200'], 2)
        self.assertEqual(result['http_non_200'], 2)
        self.assertEqual(result['network_errors'], 2)
        self.assertEqual(result['http_status_counts'], {'200': 2, '401': 1, '429': 1})
        self.assertNotIn('private details', str(result))

class LikeReferenceUpdateTests(unittest.IsolatedAsyncioTestCase):
    def test_timestamp_is_generated_for_each_request(self):
        with patch.object(lssj.time, 'time', side_effect=[1800000000, 1800000001]):
            self.assertEqual(lssj.like_headers('test')['X-GA-SV'], '1800000000')
            self.assertEqual(lssj.like_headers('test')['X-GA-SV'], '1800000001')

    async def test_sg_reads_and_sends_use_reference_server(self):
        client = AsyncMock()
        client.post.return_value = Mock(content=lssj.like_count_pb2.Info().SerializeToString(), status_code=401)
        with patch.object(lssj.httpx, 'AsyncClient') as factory:
            factory.return_value.__aenter__.return_value = client
            await lssj.fetch_like_info('123', 'SG', 'token')
            read = client.post.await_args
            self.assertEqual(read.args[0], 'https://clientbp.ppmainecoonghj.com/GetPlayerPersonalShow')
            self.assertEqual(read.kwargs['headers']['X-Unity-Version'], '2018.4.12f1')
            result = await lssj.send_like_requests('123', 'SG', tokens=['token'])
            self.assertEqual(result, [401])
            self.assertEqual(client.post.await_args.args[0], 'https://clientbp.ppmainecoonghj.com/LikeProfile')
            self.assertEqual(client.post.await_count, 2)  # No retry of the rejected send.

    def test_failures_identify_exact_tokens_without_exposing_them(self):
        import hashlib
        tokens = ['Bearer private-token-one', 'Bearer private-token-two', 'Bearer private-token-three']
        summary = lssj.summarize_like_results([200, 401, 'ReadTimeout'], tokens)
        self.assertEqual([item['token_index'] for item in summary['failed_tokens']], [2, 3])
        self.assertEqual(summary['failed_tokens'][0]['token_fingerprint'], hashlib.sha256(b'private-token-two').hexdigest()[:16])
        self.assertEqual(summary['failed_tokens'][0]['http_status'], 401)
        self.assertNotIn('private-token', str(summary))


if __name__ == '__main__':
    unittest.main()
