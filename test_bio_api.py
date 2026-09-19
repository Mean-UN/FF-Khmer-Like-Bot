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
        for region, host in [('SG','clientbp.ggblueshark.com'), ('BR','client.us.freefiremobile.com'), ('IND','client.ind.freefiremobile.com')]:
            session = Mock()
            with patch.object(lssj,'http_session',session):
                lssj.update_social_bio(self.token(region),'hello')
            args = session.post.call_args
            self.assertEqual(args.args[0],f'https://{host}/UpdateSocialBasicInfo')
            self.assertNotIn('verify',args.kwargs)
            self.assertEqual(args.kwargs['headers']['ReleaseVersion'],'OB55')
            plain = unpad(AES.new(lssj.G,AES.MODE_CBC,lssj.F).decrypt(args.kwargs['data']),16)
            self.assertTrue(plain.endswith(b'\x82\x01\x00'))
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

    def test_login_uses_shared_protocol(self):
        with patch.object(lssj.jwt_protocol,'major_login',return_value={'token':'jwt'}) as login:
            self.assertEqual(lssj.bio_major_login('access','open'),('jwt',4))
            login.assert_called_once_with(lssj.http_session,'open','access')

if __name__ == '__main__': unittest.main()
