import unittest
from unittest.mock import patch, AsyncMock
import lssj

class RegionSelectionTests(unittest.TestCase):
    def setUp(self):
        self.client = lssj.app.test_client()

    def test_explicit_region_skips_lookup_and_cache(self):
        with patch.object(lssj,'get_cached_region') as cache, patch.object(lssj,'fetch_player_personal_show') as lookup, patch.object(lssj,'load_like_tokens',return_value=[]):
            response=self.client.get('/like?uid=18003577777&region=%20sg%20')
        self.assertEqual(response.status_code,503)
        self.assertIn('No like tokens',response.json['error'])
        cache.assert_not_called(); lookup.assert_not_called()

    def test_failed_lookup_is_not_unsupported_region(self):
        with patch.object(lssj,'get_cached_region',return_value=None), patch.object(lssj,'fetch_player_personal_show',return_value=(None,None)), patch.object(lssj,'send_like_requests') as send:
            response=self.client.get('/likeff?uid=18003577777')
        self.assertEqual(response.status_code,502)
        self.assertEqual(response.json['code'],'REGION_LOOKUP_FAILED')
        send.assert_not_called()

    def test_invalid_explicit_region_fails_before_lookup(self):
        with patch.object(lssj,'fetch_player_personal_show') as lookup:
            response=self.client.get('/likeff?uid=123&region=invalid')
        self.assertEqual(response.status_code,400)
        lookup.assert_not_called()

    def test_detected_region_normalized_and_cached(self):
        with patch.object(lssj,'get_cached_region',return_value='invalid'), patch.object(lssj,'fetch_player_personal_show',return_value=({'basicInfo':{'region':' sg '}},'BD')), patch.object(lssj,'set_cached_region') as cache, patch.object(lssj,'load_like_tokens',return_value=[]):
            response=self.client.get('/like?uid=123')
        self.assertEqual(response.status_code,503)
        cache.assert_called_once_with('123','SG')

class RegionalLoginTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_new_protocol_and_preserves_cache_contract(self):
        with patch.dict(lssj.TOKENS,clear=True), patch.object(lssj.jwt_protocol,'generate_access_token',return_value=({},'open','access')) as auth, patch.object(lssj.jwt_protocol,'major_login',return_value={'token':'jwt','server_url':'https://example.test/','lock_region':'SG','ttl':60}):
            await lssj.Bmw('SG')
            token,region,server=await lssj.RtY('SG')
            self.assertEqual((token,region,server),('Bearer jwt','SG','https://example.test'))
            auth.assert_called_once()


class SharedProfileLookupTests(unittest.TestCase):
    def test_ffinfo_saves_region_and_uid_only_like_reuses_it(self):
        import tempfile
        from pathlib import Path
        uid = '16306497171'
        with tempfile.TemporaryDirectory() as folder, patch.object(lssj, 'REGION_CACHE_FILE', str(Path(folder) / 'regions.json')), patch.dict(lssj.UID_MEMORY, clear=True), patch.object(lssj, 'LoL', new_callable=AsyncMock, return_value={'basicInfo': {'accountId': uid, 'region': 'SG'}}) as profile:
            client = lssj.app.test_client()
            response = client.get('/meanffinfo?uid=' + uid)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(lssj.get_cached_region(uid), 'SG')
            self.assertEqual(lssj.UID_MEMORY[uid], 'SG')
            with patch.object(lssj, 'fetch_player_personal_show') as lookup, patch.object(lssj, 'load_like_tokens', return_value=[]):
                response = client.get('/like?uid=' + uid)
                self.assertEqual(response.status_code, 503)
                self.assertIn('No like tokens', response.json['error'])
                lookup.assert_not_called()

    def test_missing_or_wrong_player_region_never_cached(self):
        for basic in ({}, {'accountId': '123', 'region': 'SG'}, {'accountId': '456'}):
            with patch.object(lssj, 'get_cached_region', return_value=None), patch.dict(lssj.UID_MEMORY, clear=True), patch.object(lssj, 'REGNS', {'SG'}), patch.object(lssj, 'LoL', new_callable=AsyncMock, return_value={'basicInfo': basic}), patch.object(lssj, 'set_cached_region') as save:
                self.assertEqual(lssj.fetch_player_personal_show('456'), (None, None))
                save.assert_not_called()

if __name__ == '__main__':
    unittest.main()
