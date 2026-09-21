import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask
from reseller_api import enqueue, install_reseller_api, process_one
from reseller_bot import ResellerFeatures
from reseller_store import ResellerStore, SellerError


class ResellerApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ResellerStore(os.path.join(self.temp.name, 'resellers.sqlite3'))
        self.store.configure('99', 'Seller', 'seller', 10)
        self.app = Flask(__name__)
        install_reseller_api(self.app, self.store)
        self.client = self.app.test_client()
        env = patch.dict(os.environ, {'RESELLER_API_KEYS': '{"99":"test-key"}'})
        env.start()
        self.addCleanup(env.stop)
        self.orders = []
        self.core = SimpleNamespace(BASE_DIR=self.temp.name, autolike_lock=threading.Lock(),
            load_autolike_orders=lambda kind: self.orders,
            save_autolike_orders=self.save,
            next_autolike_order_id=lambda orders: str(len(orders) + 1),
            next_autolike_run_date=lambda **kw: '2099-01-01',
            call_api=Mock(return_value={'success': True, 'LikesGivenByAPI': 0}),
            deliver_autolike_order_now=Mock(),
            bot=SimpleNamespace(token='1:secret'), logger=Mock())
        self.features = ResellerFeatures(self.core)

    def save(self, orders, kind):
        self.orders = orders

    def submit(self, total=220, key='one', uid='123', headers=True):
        return self.client.get('/autolikeff', query_string={
            'uid': uid, 'total': total, 'seller': '99', 'request_id': key},
            headers={'Authorization': 'Bearer test-key'} if headers else {})

    def test_auth_and_packages(self):
        self.assertEqual(self.submit(headers=False).status_code, 401)
        self.assertEqual(self.submit(total=200).status_code, 400)
        self.assertEqual(self.store.report('99')[0]['remaining'], 10)

    def test_same_uid_without_request_id_creates_then_extends(self):
        params = {'uid': '123', 'total': '1000', 'seller': '99'}
        headers = {'Authorization': 'Bearer test-key'}
        first = self.client.get('/autolikeff', query_string=params, headers=headers)
        second = self.client.get('/autolikeff', query_string=params, headers=headers)
        self.assertEqual((first.status_code, second.status_code), (202, 202))
        self.assertNotEqual(first.json['request_id'], second.json['request_id'])
        process_one(self.features)
        process_one(self.features)
        self.assertEqual(len(self.orders), 1)
        self.assertEqual(self.orders[0]['total_likes'], 2000)
        report = self.store.report('99')[0]
        self.assertEqual((report['remaining'], report['cents']), (8, 100))
        status = self.client.get('/autolikeff/status', query_string={
            'seller': '99', 'request_id': second.json['request_id']}, headers=headers)
        self.assertEqual(status.json['result']['action'], 'extended')

    def test_duplicate_request_does_not_charge_twice(self):
        self.assertEqual(self.submit().status_code, 202)
        self.assertEqual(self.submit().status_code, 202)
        self.assertEqual(self.submit(total=1000).status_code, 400)
        self.assertEqual(self.store.report('99')[0]['remaining'], 9)
        process_one(self.features)
        self.assertFalse(process_one(self.features))
        self.core.call_api.assert_called_once()
        self.assertEqual(self.store.report('99')[0]['cents'], 20)

    def test_low_delivery_queues_exactly_200(self):
        for count in (0, 1, 100):
            self.core.call_api.return_value = {'success': True, 'LikesGivenByAPI': count}
            self.submit(key=str(count), uid=str(1000 + count))
            process_one(self.features)
            self.assertEqual(self.orders[-1]['total_likes'], 200)
            self.assertEqual(self.orders[-1]['sent_likes'], 0)
        self.assertEqual(self.store.report('99')[0]['cents'], 60)

    def test_over_100_does_not_queue(self):
        for count in (101, 220):
            self.core.call_api.return_value = {'success': True, 'LikesGivenByAPI': count}
            self.submit(key=str(count))
            process_one(self.features)
        self.assertEqual(self.orders, [])
        self.assertEqual(self.store.report('99')[0]['cents'], 40)

    def test_recovery_defers_existing_order_and_keeps_initial_delivery(self):
        self.submit(total=1000)
        process_one(self.features)
        self.core.call_api.return_value = {'success': True, 'LikesGivenByAPI': 50}
        self.submit(key='recovery')
        process_one(self.features)
        order = self.orders[0]
        self.assertEqual(order['total_likes'], 1220)
        self.assertEqual(order['last_attempt_period'], self.store.now().date().isoformat())
        extension = order['seller_extensions'][0]
        self.assertEqual(extension['initial_likes'], 50)
        order['sent_likes'] = extension['offset'] + 220
        self.store.record_order(order)
        events = self.store.report('99')[0]['events']
        recovery = next(e for e in events if e['event_id'].endswith(':recovery'))
        self.assertEqual(recovery['likes'], 220)

    def test_disabled_seller_after_enqueue_releases_request(self):
        self.submit()
        self.store.disable('99')
        process_one(self.features)
        self.core.call_api.assert_not_called()
        self.assertEqual(self.store.report('99')[0]['remaining'], 10)

    def test_packages_and_recovery_extend_same_order(self):
        self.submit(total=1000)
        process_one(self.features)
        self.core.call_api.assert_not_called()
        self.submit(key='two')
        process_one(self.features)
        self.assertEqual(len(self.orders), 1)
        self.assertEqual(self.orders[0]['total_likes'], 1220)
        self.submit(total=1000, key='three')
        process_one(self.features)
        self.assertEqual(self.orders[0]['total_likes'], 2220)
        report = self.store.report('99')[0]
        self.assertEqual((report['remaining'], report['cents']), (8, 120))
        self.features.reconcile_orders(self.orders)
        self.assertEqual(self.orders[0]['total_likes'], 2220)

    def test_unknown_delivery_does_not_create_recovery(self):
        self.core.call_api.return_value = {'success': False, 'error': 'timeout'}
        self.submit()
        process_one(self.features)
        self.assertEqual(self.orders, [])
        response = self.client.get('/autolikeff/status?seller=99&request_id=one',
                                   headers={'Authorization': 'Bearer test-key'})
        self.assertEqual(response.json['state'], 'unknown')
        self.assertFalse(response.json['success'])
        self.assertEqual(self.store.report('99')[0]['cents'], 0)

    def test_zero_likes_releases_request_but_preserves_recovery_and_bill(self):
        with self.store.db() as db:
            db.execute("UPDATE sellers SET granted_requests=1 WHERE user_id='99'")
        self.assertEqual(self.submit().status_code, 202)
        process_one(self.features)
        report = self.store.report('99')[0]
        self.assertEqual((report['remaining'], report['used'], report['cents']), (1, 0, 20))
        self.assertEqual(self.orders[0]['total_likes'], 200)
        # Replaying the same purchase cannot refund the request twice.
        self.submit()
        self.assertFalse(process_one(self.features))
        self.assertEqual(self.store.report('99')[0]['remaining'], 1)
        # A later purchase with actual delivery still consumes the request.
        self.core.call_api.return_value = {'success': True, 'LikesGivenByAPI': 1}
        self.assertEqual(self.submit(key='positive').status_code, 202)
        process_one(self.features)
        self.assertEqual(self.store.report('99')[0]['remaining'], 0)
        self.assertEqual(self.orders[0]['total_likes'], 420)

    def test_other_seller_order_rejected_before_delivery(self):
        self.orders.append({'uid': '123', 'created_by': 'other', 'status': 'active', 'seller_event_id': 'other'})
        self.submit()
        process_one(self.features)
        self.core.call_api.assert_not_called()
        self.assertEqual(self.store.report('99')[0]['remaining'], 10)

    def test_owner_must_grant_requests(self):
        self.store.disable('99')
        self.assertEqual(self.submit().status_code, 400)

    def test_new_package_delivers_immediately_but_extension_does_not(self):
        self.submit(total=1000)
        process_one(self.features)
        self.core.deliver_autolike_order_now.assert_called_once_with(
            '1', 'likeff', expected_order=self.orders[0])
        self.assertTrue(self.orders[0]['immediate_first_delivery'])
        self.submit(total=1000, key='extension')
        process_one(self.features)
        self.core.deliver_autolike_order_now.assert_called_once()

    def test_recovery_does_not_repeat_immediate_delivery(self):
        self.submit()
        process_one(self.features)
        self.core.call_api.assert_called_once()
        self.core.deliver_autolike_order_now.assert_not_called()
        self.assertFalse(self.orders[0]['immediate_first_delivery'])

    def test_api_delivery_update_reaches_configured_groups(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path('telegram_bot.py').read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'notify_autolike_order')
        bot = Mock()
        namespace = dict(bot=bot, user_bot=None, resellers=SimpleNamespace(store=Mock()),
                         logger=Mock(), load_autolike_groups=lambda: ['-100123', '-100456'])
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'telegram_bot.py', 'exec'), namespace)
        namespace['notify_autolike_order'](
            {'seller_event_id': 'api:99:one', 'telegram_user_id': '99', 'group_id': '-100123'},
            'Daily AutoLike Update', 'Private update')
        self.assertEqual([c.args[0] for c in bot.send_message.call_args_list], [99, -100123, -100456])
        self.assertEqual(bot.send_message.call_args_list[1].args[1], 'Daily AutoLike Update')

    def test_api_purchase_alerts_owner_and_configured_groups_with_retry(self):
        self.core.OWNER_ID = 7
        self.core.load_autolike_groups = lambda: ['-100123', '-100123']
        self.core.bot.send_message = Mock(side_effect=[None, RuntimeError('offline')])
        self.submit(total=1000)
        process_one(self.features)
        self.assertEqual([c.args[0] for c in self.core.bot.send_message.call_args_list], [7, -100123])
        self.core.bot.send_message.reset_mock(side_effect=True)
        restarted = ResellerFeatures(self.core)
        restarted.send_owner_alerts()
        self.core.bot.send_message.assert_called_once()
        self.assertEqual(self.core.bot.send_message.call_args.args[0], -100123)
        text = self.core.bot.send_message.call_args.args[1]
        for value in ('AUTOLIKEFF ORDER CREATED', 'Seller', '123', '1,000', 'First delivery is processing now.'):
            self.assertIn(value, text)
        self.assertNotIn('$0.50', text)
        restarted.send_owner_alerts()
        self.core.bot.send_message.assert_called_once()
        self.assertEqual(self.store.report('99')[0]['cents'], 50)

    def test_like_group_format_and_private_billing(self):
        self.core.OWNER_ID = 7
        self.core.load_autolike_groups = lambda: ['-100123']
        self.core.bot.send_message = Mock()
        self.core.call_api.return_value = {'success': True, 'LikesGivenByAPI': 220,
            'PlayerNickname': 'Jee<Janee', 'Region': 'SG',
            'LikesbeforeCommand': 2568, 'LikesafterCommand': 2788}
        self.submit()
        process_one(self.features)
        self.features.send_owner_alerts()
        private, group = self.core.bot.send_message.call_args_list
        self.assertIn('Charge: $0.20', private.args[1])
        for text in ('Like Request Processed Successfully', 'Jee&lt;Janee', '2568', '2788', 'Likes Added: 220', '@Mean_Un'):
            self.assertIn(text, group.args[1])
        self.assertNotIn('Charge:', group.args[1])
        self.assertEqual(group.kwargs['parse_mode'], 'HTML')

    def test_extension_group_uses_existing_order_formatter(self):
        self.core.OWNER_ID = 7
        self.core.load_autolike_groups = lambda: ['-100123']
        self.core.bot.send_message = Mock()
        self.core.format_autolike_order = Mock(return_value='✅ AUTOLIKEFF ORDER EXTENDED')
        self.submit(total=1000)
        process_one(self.features)
        self.features.send_owner_alerts()
        self.submit(total=1000, key='extension')
        process_one(self.features)
        self.features.send_owner_alerts()
        call = self.core.format_autolike_order.call_args
        self.assertEqual(call.args[0]['total_likes'], 2000)
        self.assertEqual(call.kwargs['title'], '✅ AUTOLIKEFF ORDER EXTENDED')

    def test_recovery_sends_separate_messages_and_retries_only_missing_part(self):
        self.core.OWNER_ID = 7
        self.core.load_autolike_groups = lambda: ['-100123']
        self.core.bot.send_message = Mock()
        self.core.format_autolike_order = Mock(return_value='✅ AUTOLIKEFF ORDER EXTENDED')
        self.submit(total=1000)
        process_one(self.features)
        self.core.bot.send_message.reset_mock()
        self.submit(key='recovery')
        process_one(self.features)
        self.core.bot.send_message.side_effect = [None, None, RuntimeError('offline')]
        self.features.send_owner_alerts()
        calls = self.core.bot.send_message.call_args_list
        self.assertEqual([c.args[0] for c in calls], [7, -100123, -100123])
        self.assertIn('Like Request Processed Successfully', calls[1].args[1])
        self.assertNotIn('ORDER EXTENDED', calls[1].args[1])
        self.assertEqual(calls[2].args[1], '✅ AUTOLIKEFF ORDER EXTENDED')
        self.core.bot.send_message.reset_mock(side_effect=True)
        ResellerFeatures(self.core).send_owner_alerts()
        self.core.bot.send_message.assert_called_once_with(
            -100123, '✅ AUTOLIKEFF ORDER EXTENDED', parse_mode='HTML')

    def test_concurrent_requests_cannot_overspend(self):
        from concurrent.futures import ThreadPoolExecutor
        self.store.configure('88', 'Limited', '', 1)
        def purchase(key):
            try:
                enqueue(self.store, '88', '123', 1000, key)
                return True
            except SellerError:
                return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(purchase, ['a', 'b'])), 1)

    def test_slow_uid_does_not_block_other_uid_or_order_lock(self):
        from concurrent.futures import ThreadPoolExecutor
        started, release = threading.Event(), threading.Event()
        def delivery(endpoint, params, **kwargs):
            if params['uid'] == '123':
                started.set()
                if not release.wait(10):
                    raise AssertionError('test did not release delivery')
            return {'success': True, 'LikesGivenByAPI': 220}
        self.core.call_api.side_effect = delivery
        self.submit(key='first')
        self.submit(key='same-uid')
        self.submit(key='other', uid='124')
        with ThreadPoolExecutor(2) as pool:
            first = pool.submit(process_one, self.features)
            try:
                self.assertTrue(started.wait(5))
                self.assertTrue(self.core.autolike_lock.acquire(blocking=False))
                self.core.autolike_lock.release()
                self.assertTrue(pool.submit(process_one, self.features).result(timeout=5))
                self.assertFalse(process_one(self.features))
                self.assertEqual([c.args[1]['uid'] for c in self.core.call_api.call_args_list], ['123', '124'])
            finally:
                release.set()
            self.assertTrue(first.result(timeout=5))
        self.assertTrue(process_one(self.features))
        self.assertEqual(self.core.call_api.call_count, 3)

    def test_status_queue_age_and_heartbeat(self):
        from datetime import timedelta
        from reseller_api import heartbeat
        now = self.store.now()
        with patch.object(self.store, 'now', return_value=now - timedelta(seconds=40)):
            response = self.submit(total=1000)
        self.assertFalse(response.json['worker_online'])
        heartbeat(self.store, 4)
        response = self.client.get('/autolikeff/status?seller=99&request_id=one',
                                   headers={'Authorization': 'Bearer test-key'})
        self.assertTrue(response.json['worker_online'])
        self.assertEqual(response.json['worker_count'], 4)
        self.assertGreaterEqual(response.json['queued_seconds'], 40)
        self.assertEqual(response.json['seller_queued'], 1)
        with patch.object(self.store, 'now', return_value=now + timedelta(seconds=60)):
            response = self.client.get('/autolikeff/status?seller=99&request_id=one',
                                       headers={'Authorization': 'Bearer test-key'})
        self.assertFalse(response.json['worker_online'])

    def test_worker_count_bounds(self):
        from reseller_api import worker_count
        for value, expected in [('8', 8), ('100', 16), ('0', 1), ('bad', 4)]:
            with patch.dict(os.environ, {'RESELLER_API_WORKERS': value}):
                self.assertEqual(worker_count(), expected)


if __name__ == '__main__':
    unittest.main()
