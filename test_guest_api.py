"""Guest API integration with real request encoding and response parsing."""
import base64
import json
import os
import unittest
from unittest.mock import Mock, patch

import lssj
from proto import MajorLoginRes_pb2


class GuestApiTests(unittest.TestCase):
    def test_reference_cookies_are_scoped_to_oauth_requests(self):
        raw = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='test-token', lock_region='SG').SerializeToString()
        with patch.dict(os.environ, {'GUEST_REGISTER_COOKIE': 'datadome=register',
                                     'GUEST_TOKEN_COOKIE': 'datadome=token'}):
            response, session = self.run_flow(raw)
        self.assertTrue(response.json['success'])
        calls = session.post.call_args_list
        self.assertEqual(calls[0].kwargs['headers']['Cookie'], 'datadome=register')
        self.assertNotIn('Cookie', calls[1].kwargs['headers'])
        for call in calls[2:]:
            self.assertNotIn('Cookie', call.kwargs['headers'])

    def test_explicit_empty_cookie_disables_reference_value(self):
        with patch.dict(os.environ, {'GUEST_REGISTER_COOKIE': '', 'GUEST_TOKEN_COOKIE': ''}):
            self.assertEqual(lssj.guest_protocol.oauth_cookie('register'), '')
            self.assertEqual(lssj.guest_protocol.oauth_cookie('token'), '')

    def test_registration_read_timeout_is_unknown_and_not_retried(self):
        session = Mock()
        session.post.side_effect = lssj.requests.ReadTimeout()
        with patch.object(lssj.requests, 'Session') as factory:
            factory.return_value.__enter__.return_value = session
            response = lssj.app.test_client().post('/createaccount', json={
                'region': 'SG', 'name': 'Example'})
        self.assertEqual(response.json['error_code'], 'upstream_read_timeout')
        self.assertTrue(response.json['registration_outcome_unknown'])
        self.assertNotIn('http_status', response.json)
        self.assertEqual(session.post.call_count, 1)

    def test_registration_rate_limit_reports_retry_after_without_retry(self):
        session = Mock()
        reply = Mock(status_code=429, headers={'Retry-After': '60'})
        reply.json.return_value = {'code': 1006, 'error': 'error_too_many_requests'}
        reply.raise_for_status.side_effect = lssj.requests.HTTPError(response=reply)
        session.post.return_value = reply
        with patch.object(lssj.requests, 'Session') as factory:
            factory.return_value.__enter__.return_value = session
            response = lssj.app.test_client().post('/createaccount', json={
                'region': 'SG', 'name': 'Example'})
        self.assertEqual(response.json['error_code'], 'upstream_rate_limited')
        self.assertEqual(response.json['retry_after'], '60')
        self.assertIn('rate limit', response.json['error'])
        self.assertEqual(session.post.call_count, 1)

    def test_token_timeout_does_not_report_registration_status(self):
        session = Mock()
        registration = Mock(status_code=200)
        registration.json.return_value = {'code': 0, 'data': {'uid': '123'}}
        session.post.side_effect = [registration] + [lssj.requests.Timeout()] * 6
        with patch.object(lssj.requests, 'Session') as factory, patch.object(lssj.time, 'sleep'):
            factory.return_value.__enter__.return_value = session
            response = lssj.app.test_client().post('/createaccount', json={
                'region': 'SG', 'name': 'Example'})
        self.assertTrue(response.json['guest_created'])
        self.assertEqual(response.json['uid'], '123')
        self.assertEqual(response.json['failed_stage'], 'Token grant')
        self.assertNotIn('http_status', response.json)
        self.assertNotIn('HTTP 200', response.json['warning'])

    def test_registration_application_error_exposes_code_without_password(self):
        session = Mock()
        reply = Mock(status_code=200)
        reply.json.return_value = {'code': 17, 'message': 'Rejected secret-password'}
        session.post.return_value = reply
        with patch.object(lssj.requests, 'Session') as factory, patch.object(
                lssj, 'generate_custom_password', return_value='secret-password'):
            factory.return_value.__enter__.return_value = session
            response = lssj.app.test_client().post('/createaccount', json={
                'region': 'SG', 'name': 'Example'})
        self.assertFalse(response.json['success'])
        self.assertEqual(response.json['failed_stage'], 'Guest register')
        self.assertEqual(response.json['upstream_error']['code'], '17')
        self.assertNotIn('secret-password', str(response.json['upstream_error']))
        self.assertEqual(session.post.call_count, 1)

    def run_flow(self, login_body, region='SG', register_body=None, refreshed_body=None):
        session = Mock()
        replies = [Mock(status_code=200) for _ in range(7)]
        replies[0].json.return_value = {'code': 0, 'data': {'uid': '123'}}
        replies[1].json.return_value = {'code': 0, 'data': {
            'access_token': 'a' * 64, 'open_id': 'o' * 32}}
        replies[2].content = lssj.build_proto({3: 456}) if register_body is None else register_body
        replies[4].content = login_body
        replies[6].content = login_body if refreshed_body is None else refreshed_body
        if register_body is not None:
            replies.pop(3)
        session.post.side_effect = replies
        with patch.object(lssj.requests, 'Session') as factory:
            factory.return_value.__enter__.return_value = session
            response = lssj.app.test_client().post('/createaccount', json={
                'region': region, 'name': 'Example'})
        return response, session

    def test_real_route_parses_login_and_matches_hosts(self):
        raw = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='test-token', lock_region='SG').SerializeToString()
        response, session = self.run_flow(raw)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])
        self.assertEqual(str(response.json['account_id']), '456')
        registration, token_grant = session.post.call_args_list[:2]
        self.assertNotIn('Authorization', token_grant.kwargs['headers'])
        self.assertEqual(token_grant.kwargs['data']['uid'], '123')
        self.assertTrue(token_grant.args[0].endswith('/oauth/guest/token/grant'))
        for call in session.post.call_args_list:
            headers = call.kwargs['headers']
            self.assertIn('X-Forwarded-For', headers)
            self.assertEqual(headers['Host'], lssj.urlparse(call.args[0]).netloc)

    def test_requested_regions_use_one_cidr_ip_in_headers_and_payload(self):
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        from guest_activation import decode_protobuf
        for region in ('NA', 'US', 'SG', 'BD', 'ME', 'TH'):
            with self.subTest(region=region):
                raw = MajorLoginRes_pb2.MajorLoginRes(
                    account_id=456, token='test-token', lock_region=region).SerializeToString()
                with patch.object(lssj, 'get_region_ip', return_value='8.1.2.3') as select_ip:
                    response, session = self.run_flow(raw, region=region)
                self.assertTrue(response.json['success'])
                select_ip.assert_called_once_with(region)
                for call in session.post.call_args_list:
                    for key in ('X-Forwarded-For', 'X-Real-IP', 'X-Client-IP', 'Client-IP',
                                'CF-Connecting-IP', 'True-Client-IP'):
                        self.assertEqual(call.kwargs['headers'][key], '8.1.2.3')
                    self.assertEqual(call.kwargs['headers']['Forwarded'], 'for=8.1.2.3')
                call = session.post.call_args_list[4]
                fields = decode_protobuf(unpad(AES.new(lssj.G, AES.MODE_CBC, lssj.F).decrypt(
                    call.kwargs['data']), 16))
                self.assertEqual(fields[20], b'8.1.2.3')

    def test_network_profile_matches_login_device(self):
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        from guest_activation import decode_protobuf
        raw = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='test-token', lock_region='SG').SerializeToString()
        response, session = self.run_flow(raw)
        self.assertTrue(response.json['success'])
        call = session.post.call_args_list[4]
        fields = decode_protobuf(unpad(AES.new(lssj.G, AES.MODE_CBC, lssj.F).decrypt(
            call.kwargs['data']), 16))
        self.assertEqual(fields[25].decode(), call.kwargs['headers']['X-Device-Model'])
        self.assertEqual(fields[11].decode(), call.kwargs['headers']['X-Network-Type'])
        self.assertEqual(fields[7], b'2.132.4')
        self.assertEqual(session.mount.call_count, 2)
        device_id = call.kwargs['headers']['X-Device-Id']
        for request_call in session.post.call_args_list:
            self.assertEqual(request_call.kwargs['headers']['X-Device-Id'], device_id)

    def test_missing_register_id_is_recovered_from_login(self):
        raw = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='test-token', lock_region='SG').SerializeToString()
        response, session = self.run_flow(raw, register_body=b'\xff')
        self.assertTrue(response.json['success'])
        self.assertEqual(str(response.json['account_id']), '456')
        self.assertEqual(session.post.call_count, 6)
        self.assertFalse(any(call.args[0].endswith('/ChooseNewbieChoice')
                             for call in session.post.call_args_list))

    def test_region_selection_uses_requested_region_and_verifies_login(self):
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        from guest_activation import decode_protobuf
        initial = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='old-token', lock_region='SG').SerializeToString()
        refreshed = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='new-token', lock_region='BD').SerializeToString()
        response, session = self.run_flow(initial, region='BD', refreshed_body=refreshed)
        self.assertEqual(response.json['region'], 'BD')
        self.assertEqual(response.json['jwt_token'], 'new-token')
        call = session.post.call_args_list[5]
        self.assertTrue(call.args[0].endswith('/ChooseRegion'))
        self.assertEqual(call.kwargs['headers']['Authorization'], 'Bearer old-token')
        fields = decode_protobuf(unpad(AES.new(lssj.G, AES.MODE_CBC, lssj.F).decrypt(
            call.kwargs['data']), 16))
        self.assertEqual(fields[1], b'BD')

    def test_me_th_hosts_match_request_headers(self):
        for region in ('ME', 'TH'):
            raw = MajorLoginRes_pb2.MajorLoginRes(
                account_id=456, token='test-token', lock_region=region).SerializeToString()
            response, session = self.run_flow(raw, region=region)
            self.assertTrue(response.json['success'])
            for call in session.post.call_args_list[2:]:
                self.assertEqual(lssj.urlparse(call.args[0]).hostname, 'loginbp.common.ggbluefox.com')
                self.assertEqual(call.kwargs['headers']['Host'], 'loginbp.common.ggbluefox.com')

    def test_sg_request_does_not_report_wrong_region_as_success(self):
        raw = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='test-token', lock_region='NA').SerializeToString()
        response, _ = self.run_flow(raw, region='SG')
        self.assertFalse(response.json['success'])
        self.assertEqual(response.json['region'], 'NA')
        self.assertFalse(response.json['region_matches_request'])
        self.assertTrue(response.json['guest_created'])
        self.assertTrue(response.json['password'])

    def test_sg_without_server_region_is_not_confirmed(self):
        raw = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='test-token').SerializeToString()
        response, _ = self.run_flow(raw, region='SG')
        self.assertFalse(response.json['success'])
        self.assertIsNone(response.json['confirmed_region'])

    def test_malformed_login_retains_credentials_without_false_success(self):
        response, session = self.run_flow(b'\xffinvalid')
        self.assertFalse(response.json['success'])
        self.assertTrue(response.json['guest_created'])
        self.assertEqual(response.json['uid'], '123')
        self.assertTrue(response.json['password'])
        self.assertEqual(response.json['failed_stage'], 'MajorLogin')
        self.assertIn('ValueError', response.json['warning'])
        self.assertEqual(session.post.call_count, 5)

    def test_jwt_with_malformed_trailing_fields_is_not_lost(self):
        claims = base64.urlsafe_b64encode(json.dumps({
            'account_id': 456, 'lock_region': 'SG'}).encode()).rstrip(b'=')
        token = b'eyJhbGciOiJIUzI1NiJ9.' + claims + b'.signature'
        raw = b'\xff' + lssj.build_proto({8: token}) + b'\xff'
        response, _ = self.run_flow(raw)
        self.assertTrue(response.json['success'])
        self.assertEqual(response.json['jwt_token'], token.decode())

    def test_region_mismatch_keeps_account_and_does_not_register_again(self):
        raw = MajorLoginRes_pb2.MajorLoginRes(
            account_id=456, token='test-token', lock_region='BD').SerializeToString()
        response, session = self.run_flow(raw)
        self.assertFalse(response.json['success'])
        self.assertFalse(response.json['region_matches_request'])
        self.assertTrue(response.json['password'])
        self.assertEqual(response.json['region'], 'BD')
        self.assertEqual(session.post.call_count, 7)


if __name__ == '__main__':
    unittest.main()
