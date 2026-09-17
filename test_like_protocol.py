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
            self.assertIn('Android 9; ASUS_Z01QD', headers['User-Agent'])
            self.assertNotIn('X-Unity-Version', headers)
        for region in ('BR', 'US', 'SAC', 'NA'):
            self.assertEqual(lssj.like_server_url(region), 'https://client.us.freefiremobile.com')
        self.assertEqual(lssj.like_server_url('ind'), 'https://client.ind.freefiremobile.com')
        self.assertEqual(lssj.like_server_url('BD'), 'https://clientbp.ggpolarbear.com')

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

if __name__ == '__main__':
    unittest.main()
