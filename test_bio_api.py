import base64
import json
import unittest
from unittest.mock import Mock, patch
import requests
import lssj
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class BioTests(unittest.TestCase):
    def token(self, region):
        payload = base64.urlsafe_b64encode(json.dumps({'account_id':123,'lock_region':region}).encode()).decode().rstrip('=')
        return 'eyJhbGciOiJIUzI1NiJ9.' + payload + '.signature'

    def test_regions_payload_and_headers(self):
        for region, host in [('SG','clientbp.ppmainecoonghj.com'), ('BD','clientbp.ppmainecoonghj.com'), ('BR','client.us.freefiremobile.com'), ('IND','client.ind.freefiremobile.com')]:
            session = Mock()
            with patch.object(lssj,'http_session',session):
                lssj.update_social_bio(self.token(region),'hello')
            args = session.post.call_args
            self.assertEqual(args.args[0],f'https://{host}/UpdateSocialBasicInfo')
            self.assertNotIn('verify',args.kwargs)
            self.assertEqual(args.kwargs['headers']['ReleaseVersion'],'OB55')
            plain = unpad(AES.new(lssj.G,AES.MODE_CBC,lssj.F).decrypt(args.kwargs['data']),16)
            self.assertFalse(plain.endswith(b'\x82\x01\x00'))
            self.assertEqual(args.kwargs['timeout'], 30)
            self.assertEqual(args.kwargs['headers']['X-Unity-Version'], '2018.4.11f1')
            self.assertEqual(args.kwargs['headers']['Expect'], '100-continue')
            decoded = lssj.BioData(); decoded.ParseFromString(plain)
            self.assertEqual(decoded.field_8,'hello')

    def test_unknown_region_does_not_send(self):
        with patch.object(lssj,'http_session') as session:
            with self.assertRaises(ValueError):
                lssj.update_social_bio(self.token('UNKNOWN'),'hello')
            session.post.assert_not_called()

    def test_rejected_update_does_not_try_other_regions(self):
        with patch.object(lssj,'http_session') as session:
            session.post.return_value.raise_for_status.side_effect = requests.HTTPError('401')
            with self.assertRaises(requests.HTTPError):
                lssj.update_social_bio(self.token('SG'),'hello')
            self.assertEqual(session.post.call_count,1)

    def test_route_accepts_bearer_and_does_not_claim_verified_storage(self):
        response = Mock(status_code=200)
        with patch.object(lssj, 'update_social_bio', return_value=(response, 'https://example.test')) as update:
            result = lssj.app.test_client().post('/bio', json={'jwt':'Bearer '+self.token('SG'), 'bio':'hello'})
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(result.json['stored'])
        self.assertEqual(update.call_args.args[0], self.token('SG'))

    def test_long_unicode_bio_is_preserved_on_both_routes(self):
        bio = '  ' + ('Long bio ?\n' * 100) + '  '
        for route in ('/bio', '/bio_upload'):
            with patch.object(lssj, 'update_social_bio', return_value=(Mock(status_code=200), 'https://example.test')) as update:
                result = lssj.app.test_client().post(route, json={'jwt': self.token('SG'), 'bio': bio})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(update.call_args.args[1], bio)
            self.assertEqual(result.json['bio'], bio)

    def test_non_string_bio_is_rejected(self):
        result = lssj.app.test_client().post('/bio', json={'jwt': self.token('SG'), 'bio': ['invalid']})
        self.assertEqual(result.status_code, 400)

    def test_inspection_supports_flat_and_wrapped_responses(self):
        for data in ({'open_id': 'open'}, {'code': 0, 'data': {'open_id': 'open'}}):
            with patch.object(lssj, 'http_session') as session:
                session.get.return_value.json.return_value = data
                self.assertEqual(lssj.get_bio_openid_from_inspect('access')[0], 'open')

    def test_unresolved_token_returns_actionable_auth_error(self):
        with patch.object(lssj, 'get_bio_openid_from_inspect', side_effect=ValueError('missing')), patch.object(lssj, 'update_social_bio') as upload:
            response = lssj.app.test_client().post('/bio', json={'token': 'abc123', 'bio': 'hello'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error_code'], 'access_token_unresolved')
        upload.assert_not_called()

    def test_explicit_open_id_skips_inspection(self):
        with patch.object(lssj, 'get_bio_openid_from_inspect') as inspect, patch.object(lssj, 'bio_major_login', return_value=(self.token('SG'), 4)), patch.object(lssj, 'update_social_bio', return_value=(Mock(status_code=200), 'https://example.test')):
            response = lssj.app.test_client().post('/bio', json={'access_token': 'abc123', 'open_id': 'open', 'bio': 'hello'})
        self.assertEqual(response.status_code, 200)
        inspect.assert_not_called()

    def test_login_uses_shared_protocol(self):
        with patch.object(lssj.jwt_protocol,'major_login',return_value={'token':'jwt'}) as login:
            self.assertEqual(lssj.bio_major_login('access','open'),('jwt',4))
            login.assert_called_once_with(lssj.http_session,'open','access')

if __name__ == '__main__': unittest.main()
