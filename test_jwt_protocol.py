import unittest
import base64
import gzip
import json
import zlib
from unittest.mock import Mock, patch
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import jwt_protocol as protocol
from proto import MajorLoginRes_pb2

class JwtProtocolTests(unittest.TestCase):
    def test_requests_do_not_share_credentials_or_nested_fields(self):
        first = protocol.build_major_login_request('first', 'first-secret')
        first.memory_available.version = 999
        second = protocol.build_major_login_request('second', 'second-secret')
        self.assertEqual((first.open_id, first.access_token), ('first', 'first-secret'))
        self.assertEqual((second.open_id, second.access_token), ('second', 'second-secret'))
        self.assertEqual(second.memory_available.version, 55)
        self.assertFalse(protocol._MAJOR_LOGIN_TEMPLATE.access_token)
        self.assertFalse(protocol._MAJOR_LOGIN_TEMPLATE.open_id)

    def test_normal_response_skips_decompression_and_decryption(self):
        raw = MajorLoginRes_pb2.MajorLoginRes(token='test-token').SerializeToString()
        with patch.object(protocol, 'decompress_body') as decompress, patch.object(protocol.AES, 'new') as aes:
            self.assertEqual(protocol.parse_login_response(raw)['token'], 'test-token')
        decompress.assert_not_called()
        aes.assert_not_called()

    def test_request_matches_reference(self):
        req = protocol.build_major_login_request('open', 'access')
        self.assertEqual((req.open_id, req.access_token, req.client_version_code), ('open', 'access', '2024010012'))
        self.assertEqual(req.memory_available.version, 55)
        session = Mock()
        session.post.return_value.content = MajorLoginRes_pb2.MajorLoginRes(token='test-token').SerializeToString()
        protocol.major_login(session, 'open', 'access')
        call = session.post.call_args
        self.assertEqual(call.args[0], protocol.MAJOR_LOGIN_URL)
        self.assertNotIn('Host', call.kwargs['headers'])
        plain = unpad(AES.new(protocol.PROTO_KEY, AES.MODE_CBC, protocol.PROTO_IV).decrypt(call.kwargs['data']), 16)
        parsed = type(req)(); parsed.ParseFromString(plain)
        self.assertEqual(parsed.access_token, 'access')

    def test_response_encodings_preserve_api_fields(self):
        raw = MajorLoginRes_pb2.MajorLoginRes(account_id=123, lock_region='SG', token='test-token', server_url='https://example.test').SerializeToString()
        encrypt = lambda b: AES.new(protocol.PROTO_KEY, AES.MODE_CBC, protocol.PROTO_IV).encrypt(pad(b, 16))
        for data in (raw, b'junk\xff'+raw, gzip.compress(raw), zlib.compress(raw), zlib.compress(raw)[2:-4], encrypt(raw), encrypt(gzip.compress(raw))):
            with self.subTest(data=data):
                parsed = protocol.parse_login_response(data)
                self.assertEqual(parsed['account_id'], '123')
                self.assertEqual(parsed['lock_region'], 'SG')
                self.assertEqual(parsed['token'], 'test-token')

    def test_missing_token_rejected(self):
        for raw in (b'', b'BR_LOGIN_VERSION_NOT_ALLOW', MajorLoginRes_pb2.MajorLoginRes(account_id=123).SerializeToString()):
            with self.assertRaises(ValueError): protocol.parse_login_response(raw)

    def test_regex_fallback_does_not_invent_region(self):
        payload = base64.urlsafe_b64encode(json.dumps({'account_id': 123}).encode()).rstrip(b'=')
        token = b'eyJhbGciOiJIUzI1NiJ9.'+payload+b'.signature'
        raw = b'\xff\x42'+bytes([len(token)])+token+b'H\x7f\xff'
        parsed = protocol.parse_login_response(raw)
        self.assertEqual(parsed['account_id'], '123')
        self.assertNotIn('lock_region', parsed)
        self.assertEqual(parsed['token'].encode(), token)

    def test_oauth_flat_and_nested(self):
        for auth in ({'open_id':'open','access_token':'access'}, {'data':{'open_id':'open','access_token':'access'}}):
            session=Mock(); session.post.return_value.json.return_value=auth
            self.assertEqual(protocol.generate_access_token(session, '123', 'pw', 'secret')[1:], ('open','access'))
            self.assertIn('data', session.post.call_args.kwargs)

class JwtRouteTests(unittest.TestCase):
    def test_routes_and_refresh(self):
        import lssj
        client=lssj.app.test_client()
        with patch.object(lssj, 'validate_like_jwt', return_value={'profile_http_status':200}), patch.object(protocol, 'generate_access_token', return_value=({'open_id':'open'}, 'open', 'access')), patch.object(protocol, 'inspect_token', return_value={'open_id':'open'}), patch.object(protocol, 'major_login', return_value={'account_id':'123', 'lock_region':'SG', 'token':'test-token'}):
            for response in (client.get('/jwt?uid=123&pw=pw'), client.post('/jwt', json={'access_token':'access'})):
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['MajorLogin']['jwt_token'], 'test-token')
            self.assertEqual(lssj.fetch_guest_jwt_for_like('123','pw')['region'], 'SG')
        self.assertEqual(client.get('/jwt').status_code, 400)
        with patch.object(protocol, 'inspect_token', return_value={'open_id':'open'}), patch.object(protocol, 'major_login', side_effect=ValueError('no token')):
            self.assertEqual(client.post('/jwt', json={'access_token':'access'}).status_code, 502)



class JwtValidationTests(unittest.TestCase):
    def token(self, **overrides):
        import time
        claims = {'account_id':123, 'lock_region':'SG', 'exp':int(time.time())+3600}
        claims.update(overrides)
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=').decode()
        return 'eyJhbGciOiJIUzI1NiJ9.'+payload+'.'+base64.urlsafe_b64encode(b'x'*32).rstrip(b'=').decode()

    def test_profile_acceptance_required(self):
        import lssj
        profile = lssj.like_count_pb2.Info()
        profile.AccountInfo.UID = 123
        session = Mock()
        session.post.return_value.content = profile.SerializeToString()
        session.post.return_value.status_code = 200
        result = lssj.validate_like_jwt(session, self.token(), '123', 'SG')
        self.assertEqual(result['profile_http_status'], 200)
        self.assertFalse(result['like_profile_verified'])
        self.assertTrue(session.post.call_args.args[0].endswith('/GetPlayerPersonalShow'))

    def test_401_never_passes_refresh(self):
        import lssj, requests
        session = Mock()
        response = Mock(status_code=401)
        session.post.return_value.raise_for_status.side_effect = requests.HTTPError(response=response)
        with patch.object(protocol, 'generate_access_token', return_value=({},'open','access')), patch.object(protocol, 'major_login', return_value={'token':self.token(),'account_id':'123','lock_region':'SG'}):
            with self.assertRaises(requests.HTTPError):
                lssj.fetch_guest_jwt_for_like('guest','password',session=session)

    def test_expired_or_mismatched_metadata_rejected_before_request(self):
        import lssj
        for token in (self.token(exp=1), self.token(exp=None), self.token(account_id=456), self.token(lock_region='BR'), self.token()+'H', 'not-a-jwt'):
            session=Mock()
            with self.subTest(token_type=token[-10:]), self.assertRaises(ValueError):
                lssj.validate_like_jwt(session, token, '123', 'SG')
            session.post.assert_not_called()

    def test_wrong_profile_cannot_validate(self):
        import lssj
        session=Mock()
        session.post.return_value.content=lssj.like_count_pb2.Info().SerializeToString()
        with self.assertRaises(ValueError):
            lssj.validate_like_jwt(session, self.token(), '123', 'SG')

    def test_unframed_regex_token_is_rejected(self):
        with self.assertRaises(ValueError):
            protocol.parse_login_response(b'\xff'+self.token().encode()+b'H\x7f\xff')

if __name__ == '__main__': unittest.main()
