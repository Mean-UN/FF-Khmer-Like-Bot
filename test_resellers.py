"""Offline tests for reseller limits, prices, permissions and bot integration."""
import ast
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from reseller_bot import ResellerFeatures
from reseller_store import ICT, ResellerStore, SellerError


class ResellerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "resellers.sqlite3")
        self.store = ResellerStore(self.path)
        self.time = datetime(2026, 9, 13, 12, tzinfo=ICT)
        self.store.now = lambda: self.time
        self.store.configure(7, "Dara Sok", "dara", 10)

    def test_shared_limit_and_zero_likes(self):
        self.store.reserve(7, "zero", "likeff", "123")
        self.store.finish_manual("zero", 0)
        for i in range(5):
            self.store.reserve(7, str(i), "likeff", "123")
            self.store.finish_manual(str(i), 220)
        for i in range(5, 10):
            self.store.reserve(7, str(i), "autolikeff", "123", 1000, {})
        report = self.store.report(7)[0]
        self.assertEqual(report["used"], 10)
        self.assertEqual(report["cents"], 350)
        with self.assertRaises(SellerError):
            self.store.reserve(7, "over", "likeff", "123")

    def test_per_purchase_pricing_not_aggregate(self):
        for i, package in enumerate([5000, 5000, 10000, 6000, 50000]):
            self.store.reserve(7, str(i), "autolikeff", "123", package, {})
        self.assertEqual(self.store.report(7)[0]["cents"], 3125)
        with self.assertRaises(ValueError):
            self.store.reserve(7, "bad", "autolikeff", "123", 1500, {})
        self.assertEqual(self.store.report(7)[0]["used"], 5)

    def test_reset_history_persistence_payment_and_identity(self):
        self.time = datetime(2026, 9, 14, 2, 59, 59, tzinfo=ICT)
        self.store.reserve(7, "a", "autolikeff", "123", 10000, {})
        self.assertEqual(self.store.day(), "2026-09-13")
        self.store.mark_paid(7, "2026-09-13")
        self.store.reserve(7, "b", "autolikeff", "124", 1000, {})
        report = self.store.report(7)[0]
        self.assertEqual(report["cents"] - report["paid"], 50)
        self.store.remember(7, "Dara New Name", "new")
        self.time += timedelta(seconds=1)
        self.assertEqual(self.store.report(7)[0]["used"], 0)
        self.assertEqual(self.store.report(7, "2026-09-13")[0]["cents"], 500)
        clone = ResellerStore(self.path)
        self.assertEqual(len(clone.history(7)), 2)
        self.assertEqual(clone.history(7)[0]["name"], "Dara Sok")
        self.assertEqual(clone.seller(7)["name"], "Dara New Name")

    def test_concurrent_requests_reserve_capacity(self):
        def reserve(i):
            try:
                return self.store.reserve(7, str(i), "likeff", "123")
            except SellerError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(20)))
        self.assertEqual(sum(item is not None for item in results), 10)
        self.assertEqual(self.store.report(7)[0]["pending"], 10)
        key = next(item for item in results if item is not None)
        self.store.finish_manual(key, 0)
        self.store.reserve(7, "new", "likeff", "123")

    def test_idempotency_and_disable(self):
        self.store.reserve(7, "a", "likeff", "123")
        self.store.finish_manual("a", 220)
        self.store.finish_manual("a", 220)
        with self.assertRaises(SellerError):
            self.store.reserve(7, "a", "likeff", "123")
        self.assertEqual(self.store.report(7)[0]["cents"], 20)
        self.store.disable(7)
        with self.assertRaises(SellerError):
            self.store.reserve(7, "b", "likeff", "123")
        self.assertEqual(len(self.store.history(7)), 1)

    def test_payment_replay_does_not_pay_later_purchases(self):
        self.store.reserve(7, "first", "autolikeff", "123", 1000, {})
        self.assertEqual(self.store.mark_paid(7, self.store.day(), command_id="paid-message"), 50)
        self.store.reserve(7, "second", "autolikeff", "124", 1000, {})
        self.assertEqual(self.store.mark_paid(7, self.store.day(), command_id="paid-message"), 50)
        report = self.store.report(7)[0]
        self.assertEqual(report["cents"] - report["paid"], 50)
        self.assertEqual(self.store.mark_paid(7, self.store.day(), command_id="new-payment"), 100)

    def test_oversized_topup_is_rejected_without_changing_credits(self):
        with self.assertRaises(SellerError):
            self.store.configure(7, "Dara Sok", "dara", 9223372036854775808)
        self.assertEqual(self.store.report(7)[0]["remaining"], 10)

    def test_exhausted_credits_stay_zero_until_owner_adds(self):
        for i in range(10):
            self.store.reserve(7, str(i), "autolikeff", "123", 1000, {})
        self.assertEqual(self.store.report(7)[0]["remaining"], 0)
        self.time += timedelta(days=1)
        self.assertEqual(self.store.report(7)[0]["used"], 0)
        self.assertEqual(self.store.report(7)[0]["remaining"], 0)
        with self.assertRaises(SellerError):
            self.store.reserve(7, "next-day", "likeff", "123")
        self.store.configure(7, "Dara Sok", "dara", 3, grant_id="topup")
        self.assertEqual(self.store.report(7)[0]["remaining"], 3)
        with self.assertRaises(SellerError):
            self.store.configure(7, "Dara Sok", "dara", 3, grant_id="topup")
        self.store.reserve(7, "after-topup", "likeff", "123")
        self.store.finish_manual("after-topup", 0)
        self.assertEqual(self.store.report(7)[0]["remaining"], 3)
        self.store.configure(7, "Dara Sok", "dara", 2, grant_id="topup2")
        self.assertEqual(self.store.report(7)[0]["remaining"], 5)

    def test_unused_credits_carry_over_and_abandoned_holds_expire(self):
        self.store.reserve(7, "positive", "likeff", "123")
        self.store.finish_manual("positive", 220)
        self.store.reserve(7, "pending", "likeff", "123")
        self.time += timedelta(days=1)
        self.assertEqual(self.store.report(7)[0]["remaining"], 9)
        self.assertEqual(self.store.report(7)[0]["pending"], 0)
        self.store.finish_manual("pending", 0)
        self.assertEqual(self.store.report(7)[0]["remaining"], 9)

    def test_legacy_daily_allowance_migrates_without_refill(self):
        for i in range(10):
            self.store.reserve(7, str(i), "autolikeff", "123", 1000, {})
        with sqlite3.connect(self.path) as db:
            db.execute("ALTER TABLE sellers RENAME COLUMN granted_requests TO daily_limit")
        db.close()
        self.time += timedelta(days=1)
        self.assertEqual(self.store.report(7)[0]["remaining"], 0)
        self.store.configure(7, "Dara Sok", "dara", 2)
        self.assertEqual(self.store.report(7)[0]["remaining"], 2)


class ResellerBotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bot = Mock(token="42:fake")
        self.messages = []
        self.orders = []
        self.core = SimpleNamespace(
            BASE_DIR=self.temp.name, bot=self.bot, user_bot=None,
            active_bot_for=lambda message: self.bot,
            command_belongs_to_other_bot=lambda *args: False,
            is_owner=lambda uid: uid == 1,
            requester_name=lambda u: " ".join(v for v in [u.first_name, u.last_name] if v),
            send_long_message=lambda message, text, **kw: self.messages.append(text),
            telegram_user_record=lambda uid: {"name": "Dara Sok", "username": "dara"},
            autolike_lock=threading.Lock(),
            find_existing_autolike_order=lambda orders, uid: next((o for o in orders if o["uid"] == uid), None),
            next_autolike_order_id=lambda orders: str(len(orders) + 1),
            next_autolike_run_date=lambda **kw: "2026-09-14",
            deliver_autolike_order_now=Mock(), logger=Mock(),
            format_autolike_order=Mock(return_value="Order extended"),
            call_api=Mock(return_value={"success": True, "LikesGivenByAPI": 220, "UID": 123}),
        )
        self.features = ResellerFeatures(self.core)
        self.core.resellers = self.features
        self.core.load_autolike_orders = lambda kind: self.features.reconcile_orders(list(self.orders))
        self.core.save_autolike_orders = lambda orders, kind: setattr(self, "orders", json.loads(json.dumps(orders)))
        self.features.store.configure(7, "Dara Sok", "dara", 10)
        self.message = SimpleNamespace(from_user=SimpleNamespace(id=7, first_name="Dara", last_name="Sok", username="dara"), chat=SimpleNamespace(id=7, type="private"), message_id=1, text="/seller")

    def test_manual_count_zero_and_timeout(self):
        result = self.features.manual_call(self.message, {"uid": "123"})
        self.assertEqual(result["seller_charge"], "$0.20")
        self.message.message_id = 2
        self.core.call_api.return_value = {"success": True, "LikesGivenByAPI": 0}
        result = self.features.manual_call(self.message, {"uid": "123"})
        self.assertEqual(result["seller_charge"], "$0.00")
        self.message.message_id = 3
        self.core.call_api.return_value = {"success": False, "error": "API timeout"}
        self.features.manual_call(self.message, {"uid": "123"})
        report = self.features.store.report(7)[0]
        self.assertEqual((report["used"], report["pending"], report["cents"]), (1, 0, 20))
        self.assertEqual(report["remaining"], 9)
        self.assertNotIn("42:7:", self.features.history_text(7, 1))
        self.message.message_id = 4
        self.core.call_api.return_value = {"success": True, "LikesGivenByAPI": 220}
        self.features.manual_call(self.message, {"uid": "123"})
        self.assertEqual(self.features.store.report(7)[0]["used"], 2)

    def test_order_uses_senders_id_charges_once_and_preserves_history(self):
        self.message.text = "/autolikeff 123 10000"
        with patch("reseller_bot.threading.Thread") as thread:
            self.features.create_order(self.message)
            thread.return_value.start.assert_called_once()
        self.assertEqual(self.orders[0]["telegram_user_id"], "7")
        self.assertEqual(self.orders[0]["telegram_user_name"], "Dara Sok")
        self.assertEqual(self.features.store.report(7)[0]["cents"], 450)
        self.assertIn("Total Likes: 10,000", self.messages[-1])
        self.assertNotIn("Charge:", self.messages[-1])
        self.assertNotIn("Daily total:", self.messages[-1])
        self.features.create_order(self.message)
        self.assertEqual(self.features.store.report(7)[0]["used"], 1)
        self.orders[0]["sent_likes"] = 10000
        self.orders[0]["status"] = "completed"
        self.features.store.record_order(self.orders[0])
        self.features.store.record_order(self.orders[0])
        self.orders.clear()
        self.assertEqual(self.features.reconcile_orders([]), [])
        history = self.features.store.history(7)
        self.assertEqual((history[0]["likes"], history[0]["cents"]), (10000, 450))

    def test_outbox_recovers_failed_export(self):
        self.message.text = "/autolikeff 123 1000"
        save = self.core.save_autolike_orders
        self.core.save_autolike_orders = Mock(side_effect=OSError("disk failure"))
        self.features.create_order(self.message)
        self.assertEqual(len(self.features.store.pending_orders()), 1)
        self.core.save_autolike_orders = save
        self.features.reconcile_orders([])
        self.assertEqual(len(self.orders), 1)
        self.assertEqual(self.features.store.pending_orders(), [])
        self.assertEqual(self.features.store.report(7)[0]["used"], 1)

    def test_uid_validation_and_normalization(self):
        for uid in ("0", "9223372036854775808"):
            self.message.text = f"/autolikeff {uid} 1000"
            self.features.create_order(self.message)
            self.assertEqual(self.features.store.report(7)[0]["used"], 0)
        self.message.text = "/autolikeff 000123 1000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        self.assertEqual(self.orders[0]["uid"], "123")
        self.message.message_id = 2
        self.message.text = "/autolikeff 123 1000"
        self.features.create_order(self.message)
        self.assertEqual(self.features.store.report(7)[0]["used"], 1)

    def test_extension_costs_one_request_and_its_own_package_price(self):
        self.message.text = "/autolikeff 123 5000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        self.message.message_id = 2
        self.message.text = "/extend 123 5000"
        self.features.extend_order(self.message)
        self.assertEqual(self.orders[0]["total_likes"], 10000)
        report = self.features.store.report(7)[0]
        self.assertEqual((report["used"], report["remaining"], report["cents"]), (2, 8, 500))
        self.assertIn("orders/extensions", self.features.format_report([report], report["day"]))
        self.features.extend_order(self.message)
        self.assertEqual(self.features.store.report(7)[0]["used"], 2)
        self.assertEqual(self.orders[0]["total_likes"], 10000)
        self.orders[0]["sent_likes"] = 5200
        self.features.store.record_order(self.orders[0])
        history = self.features.store.history(7)
        self.assertEqual(next(e for e in history if e["kind"] == "autolikeff")["likes"], 5000)
        self.assertEqual(next(e for e in history if e["kind"] == "autolikeff_extend")["likes"], 200)
        self.assertEqual(self.features.store.report(7)[0]["cents"], 500)

    def test_extension_permissions_packages_and_exhausted_credits(self):
        self.message.text = "/autolikeff 123 1000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        self.features.store.configure(8, "Other Seller", "", 10)
        self.message.from_user.id = 8
        self.message.text = "/extend 123 1000"
        self.features.extend_order(self.message)
        self.assertEqual(self.features.store.report(8)[0]["used"], 0)
        self.message.from_user.id = 7
        self.message.message_id = 2
        self.message.text = "/extend 123 1500"
        self.features.extend_order(self.message)
        self.assertEqual(self.features.store.report(7)[0]["used"], 1)
        for i in range(9):
            self.features.store.reserve(7, f"filler{i}", "likeff", "456")
            self.features.store.finish_manual(f"filler{i}", 220)
        self.message.text = "/extend 123 1000"
        self.features.extend_order(self.message)
        self.assertEqual(self.orders[0]["total_likes"], 1000)
        self.assertEqual(self.features.store.report(7)[0]["used"], 10)
        self.assertIn("No reseller requests available", self.messages[-1])

    def test_extension_export_recovery_does_not_add_likes_twice(self):
        self.message.text = "/autolikeff 123 1000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        self.message.message_id = 2
        self.message.text = "/extend 123 2000"
        with patch.object(self.features.store, "exported", side_effect=OSError("interrupted")):
            self.features.extend_order(self.message)
        self.assertEqual(self.orders[0]["total_likes"], 3000)
        self.features.reconcile_orders(list(self.orders))
        self.assertEqual(self.orders[0]["total_likes"], 3000)
        self.assertEqual(self.features.store.report(7)[0]["used"], 2)
        self.assertEqual(self.features.store.pending_orders(), [])

    def test_extension_on_later_day_keeps_paid_bills_separate(self):
        store = self.features.store
        store.now = lambda: datetime(2026, 9, 13, 12, tzinfo=ICT)
        self.message.text = "/autolikeff 123 10000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        self.assertEqual(store.mark_paid(7, "2026-09-13", "pay-day-one"), 450)

        store.now = lambda: datetime(2026, 9, 14, 12, tzinfo=ICT)
        self.message.message_id = 2
        self.message.text = "/extend 123 1000"
        self.features.extend_order(self.message)
        yesterday = store.report(7, "2026-09-13")[0]
        today = store.report(7, "2026-09-14")[0]
        self.assertEqual((yesterday["used"], yesterday["cents"], yesterday["paid"]), (1, 450, 450))
        self.assertEqual((today["used"], today["cents"], today["paid"]), (1, 50, 0))
        self.assertEqual(store.mark_paid(7, "2026-09-14", "pay-day-two"), 50)

        self.message.message_id = 3
        self.message.text = "/extend 123 2000"
        self.features.extend_order(self.message)
        today = store.report(7, "2026-09-14")[0]
        self.assertEqual((today["cents"], today["paid"]), (150, 50))
        self.assertEqual(today["cents"] - today["paid"], 100)
        # Neither replaying today's payment nor paying yesterday clears the
        # extension bought after today's payment.
        store.mark_paid(7, "2026-09-14", "pay-day-two")
        store.mark_paid(7, "2026-09-13", "pay-yesterday-again")
        self.assertEqual(store.report(7, "2026-09-14")[0]["paid"], 50)
        self.assertEqual(store.report(7, "2026-09-13")[0]["cents"], 450)
        self.assertEqual(store.report(7)[0]["remaining"], 7)

    def test_extension_uses_billing_day_at_three_am_boundary(self):
        store = self.features.store
        store.now = lambda: datetime(2026, 9, 13, 12, tzinfo=ICT)
        self.message.text = "/autolikeff 123 1000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        store.now = lambda: datetime(2026, 9, 14, 2, 59, 59, tzinfo=ICT)
        self.message.message_id = 2
        self.message.text = "/extend 123 1000"
        self.features.extend_order(self.message)
        store.now = lambda: datetime(2026, 9, 14, 3, 0, 0, tzinfo=ICT)
        self.message.message_id = 3
        self.features.extend_order(self.message)
        self.assertEqual(store.report(7, "2026-09-13")[0]["cents"], 100)
        self.assertEqual(store.report(7, "2026-09-14")[0]["cents"], 50)

    def test_permission_and_report_isolation(self):
        self.features.store.configure(8, "Other Seller", "other", 10)
        self.features.store.reserve(8, "other", "autolikeff", "999", 50000, {})
        self.features.command(self.message)
        self.assertIn("Dara Sok", self.messages[-1])
        self.assertNotIn("Other Seller", self.messages[-1])
        self.message.text = "/seller 8 100"
        self.features.command(self.message)
        self.assertEqual(self.features.store.seller(8)["granted_requests"], 10)
        self.message.text = "/seller paid 8 2026-09-13"
        self.features.command(self.message)
        self.assertEqual(self.features.store.report(8)[0]["paid"], 0)
        self.message.from_user.id = 1
        self.message.text = "/seller summary"
        self.features.command(self.message)
        self.assertIn("Other Seller", self.messages[-1])

    def test_actual_manual_bot_function_uses_seller_limit(self):
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_like")
        node.decorator_list = []
        namespace = dict(vars(self.core), datetime=datetime, timedelta=timedelta, CAMBODIA_TZ=ICT,
                         usage_tracker={}, usage_reset_period=lambda now: now.date(), get_user_limit=lambda uid: 1,
                         resolve_like_region=lambda *a: ("SG", "cache"), owner_contact_text=lambda: "Owner",
                         remember_like_success=Mock(), format_next_like_wait=lambda *a: "Tomorrow")
        exec(compile(ast.Module(body=[node], type_ignores=[]), "telegram_bot.py", "exec"), namespace)
        for number in range(1, 4):
            self.message.message_id = number
            namespace["process_like"](self.message, "likeff", "123", active_bot=self.bot)
        self.assertEqual(self.features.store.report(7)[0]["used"], 3)
        self.assertEqual(namespace["usage_tracker"], {})
        text = self.bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("Like Request Processed Successfully", text)
        self.assertIn("Requests Left: 7", text)
        self.assertNotIn("Charge:", text)
        self.assertNotIn("Daily total:", text)
        self.message.message_id = 4
        self.core.call_api.return_value = {"success": True, "LikesGivenByAPI": 0}
        namespace["process_like"](self.message, "likeff", "123", active_bot=self.bot)
        text = self.bot.edit_message_text.call_args.kwargs["text"]
        self.assertIn("Already Received Maximum Free Likes", text)
        self.assertNotIn("Charged:", text)
        self.assertEqual(self.features.store.report(7)[0]["used"], 3)


class DeliveryCoordinationTests(unittest.TestCase):
    def setUp(self):
        self.order = {"order_id": "1", "uid": "123", "created_at": "today", "status": "active", "total_likes": 220, "sent_likes": 0, "next_run_date": "2026-09-13"}
        self.orders = [dict(self.order)]
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("deliver_autolike_order_now", "autolike_order_status")]
        for node in nodes:
            node.decorator_list = []
        self.ns = dict(autolike_lock=threading.Lock(),
                       load_autolike_orders=lambda kind: json.loads(json.dumps(self.orders)),
                       save_autolike_orders=lambda orders, kind: setattr(self, "orders", json.loads(json.dumps(orders))),
                       current_autolike_period=lambda: "2026-09-13",
                       resellers=Mock(), deliver_autolike_order=Mock(side_effect=self.complete))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "telegram_bot.py", "exec"), self.ns)

    def complete(self, order, *args, **kwargs):
        order.update(sent_likes=220, status="completed", remove_after_save=True)

    def run_order(self, **kwargs):
        return self.ns["deliver_autolike_order_now"]("1", **kwargs)

    def test_concurrent_immediate_and_scheduled_delivery_only_submit_once(self):
        started, release = threading.Event(), threading.Event()
        def blocked(order, *args, **kwargs):
            started.set()
            if not release.wait(5):
                raise AssertionError("Test delivery did not release")
            self.complete(order)
        self.ns["deliver_autolike_order"].side_effect = blocked
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.run_order)
            try:
                self.assertTrue(started.wait(5))
                self.assertFalse(self.run_order(period="2026-09-13", expected_order=self.order))
            finally:
                release.set()
            self.assertTrue(first.result(timeout=5))
        self.ns["deliver_autolike_order"].assert_called_once()
        self.assertEqual(self.orders, [])

    def test_deleted_order_is_not_restored(self):
        def deleted(order, *args, **kwargs):
            self.orders = []
            self.complete(order)
        self.ns["deliver_autolike_order"].side_effect = deleted
        self.run_order()
        self.assertEqual(self.orders, [])

    def test_extension_during_delivery_is_preserved(self):
        def extended(order, *args, **kwargs):
            self.orders[0]["total_likes"] = 1000
            self.orders[0]["seller_extensions"] = [{"event_id": "extension", "offset": 220}]
            self.complete(order)
        self.ns["deliver_autolike_order"].side_effect = extended
        self.run_order()
        self.assertEqual(self.orders[0]["total_likes"], 1000)
        self.assertEqual(self.orders[0]["sent_likes"], 220)
        self.assertEqual(self.orders[0]["status"], "active")
        self.assertEqual(self.orders[0]["seller_extensions"][0]["event_id"], "extension")

    def test_reused_id_or_future_schedule_not_submitted(self):
        self.assertFalse(self.run_order(expected_order={**self.order, "uid": "different"}))
        self.orders[0]["next_run_date"] = "2026-09-14"
        self.assertFalse(self.run_order(period="2026-09-13"))
        self.ns["deliver_autolike_order"].assert_not_called()

    def test_reminder_preserves_progress_and_uses_correct_bot(self):
        class StopLoop(BaseException):
            pass
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_autolikeff_near_end_notices")
        self.orders[0].update(telegram_user_id="7", notification_bot_id="200")
        user_bot = Mock(token="200:fake")
        user_bot.send_message.side_effect = lambda *a, **kw: self.orders[0].update(sent_likes=100)
        ns = dict(self.ns, datetime=datetime, CAMBODIA_TZ=ICT, bot=Mock(), user_bot=user_bot,
                  autolike_notice_datetime=lambda now: now - timedelta(hours=1),
                  current_autolike_period=lambda *a: "2026-09-13",
                  load_autolike_orders=lambda: json.loads(json.dumps(self.orders)),
                  save_autolike_orders=lambda orders: setattr(self, "orders", json.loads(json.dumps(orders))),
                  AUTOLIKEFF_NEAR_END_THRESHOLD=660, AUTOLIKEFF_CHECK_INTERVAL=60,
                  format_autolike_near_end_notice=lambda order: "Reminder", logger=Mock(),
                  time=SimpleNamespace(sleep=Mock(side_effect=StopLoop)))
        exec(compile(ast.Module(body=[node], type_ignores=[]), "telegram_bot.py", "exec"), ns)
        with self.assertRaises(StopLoop):
            ns["process_autolikeff_near_end_notices"]()
        self.assertEqual(self.orders[0]["sent_likes"], 100)
        self.assertEqual(self.orders[0]["last_near_end_notice_period"], "2026-09-13")
        user_bot.send_message.assert_called_once_with(7, "Reminder", parse_mode=None)
        ns["bot"].send_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
