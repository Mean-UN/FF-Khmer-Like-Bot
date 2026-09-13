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


class TestKeyboard:
    def __init__(self, **kwargs):
        self.keyboard = []

    def row(self, *buttons):
        self.keyboard.append(list(buttons))


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
            BASE_DIR=self.temp.name, bot=self.bot, user_bot=None, OWNER_ID=1,
            active_bot_for=lambda message: self.bot,
            command_belongs_to_other_bot=lambda *args: False,
            is_owner=lambda uid: uid == 1,
            requester_name=lambda u: " ".join(v for v in [u.first_name, u.last_name] if v),
            send_long_message=lambda message, text, **kw: self.messages.append(text),
            telegram_user_record=lambda uid: {"name": "Dara Sok", "username": "dara"},
            resolve_autolike_group_id=lambda message: str(message.chat.id) if message.chat.type in ("group", "supergroup") else "",
            autolike_lock=threading.Lock(),
            find_existing_autolike_order=lambda orders, uid: next((o for o in orders if o["uid"] == uid), None),
            next_autolike_order_id=lambda orders: str(len(orders) + 1),
            next_autolike_run_date=lambda **kw: "2026-09-14",
            deliver_autolike_order_now=Mock(), logger=Mock(),
            InlineKeyboardMarkup=TestKeyboard,
            InlineKeyboardButton=lambda text, callback_data: SimpleNamespace(text=text, callback_data=callback_data),
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

    def test_owner_alert_only_for_successful_manual_requests(self):
        self.features.manual_call(self.message, {"uid": "123"})
        self.features.manual_call(self.message, {"uid": "123"})
        self.message.message_id = 2
        self.core.call_api.return_value = {"success": True, "LikesGivenByAPI": 0}
        self.features.manual_call(self.message, {"uid": "123"})
        self.message.message_id = 3
        self.core.call_api.return_value = {"success": False, "error": "API timeout"}
        self.features.manual_call(self.message, {"uid": "123"})
        self.features.send_owner_alerts()
        self.bot.send_message.assert_called_once()
        args = self.bot.send_message.call_args.args
        self.assertEqual(args[0], 1)
        self.assertIn("Dara Sok", args[1])
        self.assertIn("Likes sent: 220", args[1])
        self.assertIn("Charge: $0.20", args[1])
        self.features.send_owner_alerts()
        self.bot.send_message.assert_called_once()

    def test_owner_alerts_for_order_and_extension_not_each_delivery(self):
        self.message.text = "/autolikeff 123 1000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        self.message.message_id = 2
        self.message.text = "/extend 123 2000"
        self.features.extend_order(self.message)
        self.orders[0]["sent_likes"] = 220
        self.features.store.record_order(self.orders[0])
        self.features.send_owner_alerts()
        self.assertEqual(self.bot.send_message.call_count, 2)
        texts = [call.args[1] for call in self.bot.send_message.call_args_list]
        self.assertTrue(any("AUTOLIKEFF ORDER" in text and "Charge: $0.50" in text for text in texts))
        self.assertTrue(any("AUTOLIKEFF EXTENSION" in text and "Charge: $1.00" in text for text in texts))
        self.orders[0]["sent_likes"] = 440
        self.features.store.record_order(self.orders[0])
        self.features.send_owner_alerts()
        self.assertEqual(self.bot.send_message.call_count, 2)

    def test_owner_alert_failure_retries_after_restart_without_recharging(self):
        self.features.manual_call(self.message, {"uid": "123"})
        self.bot.send_message.side_effect = RuntimeError("Telegram unavailable")
        self.features.send_owner_alerts()
        self.assertEqual(len(self.features.store.pending_owner_alerts()), 1)
        restarted = ResellerFeatures(self.core)
        self.bot.send_message.side_effect = None
        restarted.send_owner_alerts()
        self.assertEqual(restarted.store.pending_owner_alerts(), [])
        self.assertEqual(restarted.store.report(7)[0]["used"], 1)
        self.assertEqual(restarted.store.report(7)[0]["cents"], 20)

    def test_order_uses_senders_id_charges_once_and_preserves_history(self):
        self.message.text = "/autolikeff 123 10000"
        with patch("reseller_bot.threading.Thread") as thread:
            self.features.create_order(self.message)
            thread.return_value.start.assert_called_once()
        self.assertEqual(self.orders[0]["telegram_user_id"], "7")
        self.assertEqual(self.orders[0]["group_id"], "")
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

    def test_group_order_sends_result_using_originating_bot(self):
        self.message.chat.type = "supergroup"
        self.message.chat.id = -100123
        self.message.text = "/autolikeff 123 1000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        self.assertEqual(self.orders[0]["group_id"], "-100123")
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "notify_autolike_order")
        primary = Mock(token="other:fake")
        ns = dict(bot=primary, user_bot=self.bot, resellers=self.features, logger=Mock())
        exec(compile(ast.Module(body=[node], type_ignores=[]), "telegram_bot.py", "exec"), ns)
        # A blocked private chat must not prevent the group result.
        self.bot.send_message.side_effect = [RuntimeError("private chat blocked"), None]
        ns["notify_autolike_order"](self.orders[0], "Group result", "Private result")
        self.bot.send_message.assert_any_call(7, "Private result", parse_mode=None)
        self.bot.send_message.assert_any_call(-100123, "Group result", parse_mode=None)
        primary.send_message.assert_not_called()

    def test_private_reseller_order_uses_assigned_group(self):
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "resolve_autolike_group_id")
        ns = {"load_autolike_groups": lambda: ["-100999"]}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "telegram_bot.py", "exec"), ns)
        self.core.resolve_autolike_group_id = ns["resolve_autolike_group_id"]
        self.message.text = "/autolikeff 123 1000"
        with patch("reseller_bot.threading.Thread"):
            self.features.create_order(self.message)
        self.assertEqual(self.orders[0]["group_id"], "-100999")
        self.assertEqual(self.orders[0]["telegram_user_id"], "7")

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

    def test_history_buttons_layout_and_page_boundaries(self):
        for i in range(15):
            key = f"history-{i}"
            self.features.store.reserve(7, key, "likeff", str(100 + i))
            self.features.store.finish_manual(key, 0)
        self.message.text = "/seller history"
        self.features.command(self.message)
        first = self.bot.reply_to.call_args
        text = first.args[1]
        self.assertEqual(text.count("👤 Dara Sok"), 1)
        self.assertIn("🆔 7", text)
        self.assertEqual(text.count("LIKEFF · UID"), 7)
        self.assertNotIn("Page", text)
        self.assertNotIn("next page number", text)
        buttons = first.kwargs["reply_markup"].keyboard[0]
        self.assertEqual([b.text for b in buttons], ["1 / 3", "Next ➡️"])
        self.assertEqual(buttons[-1].callback_data, "sellerhist:7:2")

        call = SimpleNamespace(id="tap", data="sellerhist:7:2", from_user=self.message.from_user, message=self.message)
        self.features.history_callback(call)
        edit = self.bot.edit_message_text.call_args.kwargs
        self.assertEqual(edit["message_id"], self.message.message_id)
        self.assertEqual(edit["text"].count("LIKEFF · UID"), 7)
        self.assertEqual([b.text for b in edit["reply_markup"].keyboard[0]], ["⬅️ Previous", "2 / 3", "Next ➡️"])
        self.assertNotIn("UID 114", edit["text"])
        call.data = "sellerhist:7:999999999999999999999999"
        self.features.history_callback(call)
        edit = self.bot.edit_message_text.call_args.kwargs
        self.assertEqual(edit["text"].count("LIKEFF · UID"), 1)
        self.assertEqual([b.text for b in edit["reply_markup"].keyboard[0]], ["⬅️ Previous", "3 / 3"])
        self.assertLess(len(edit["text"].encode("utf-16-le")) // 2, 4096)

    def test_history_callback_access_and_empty_history(self):
        call = SimpleNamespace(id="tap", data="sellerhist:8:1", from_user=self.message.from_user, message=self.message)
        self.features.history_callback(call)
        self.bot.edit_message_text.assert_not_called()
        self.assertTrue(self.bot.answer_callback_query.call_args.kwargs["show_alert"])
        call.from_user = SimpleNamespace(id=1)
        self.features.history_callback(call)
        self.assertIn("No history yet.", self.bot.edit_message_text.call_args.kwargs["text"])
        self.assertIsNone(self.bot.edit_message_text.call_args.kwargs["reply_markup"])
        call.data = "sellerhist:7:bad"
        self.bot.edit_message_text.reset_mock()
        self.features.history_callback(call)
        self.bot.edit_message_text.assert_not_called()



class DailyBillTests(unittest.TestCase):
    def setUp(self):
        ResellerBotTests.setUp(self)
        self.now = datetime(2026, 9, 13, 12, tzinfo=ICT)
        self.features.store.now = lambda: self.now
        self.bot.send_message.return_value = SimpleNamespace(message_id=500)
        self.features.send_daily_bills()

    def purchase(self, key="purchase", package=1000):
        self.features.store.reserve(7, key, "autolikeff", "123", package, {})

    def partial_command(self, amount="0.20", message_id=500):
        self.message.from_user.id = 1
        self.message.chat.id = 1
        self.message.message_id = message_id
        self.message.text = f"/seller paid 7 {amount}"
        self.bot.send_message.return_value = SimpleNamespace(message_id=message_id)
        self.features.command(self.message)
        data = self.bot.send_message.call_args.kwargs["reply_markup"].keyboard[0][0].callback_data
        call = self.bill_call(data)
        call.message.message_id = message_id
        return call

    def test_partial_payment_confirmation_replay_and_audit(self):
        self.purchase()
        call = self.partial_command()
        self.assertEqual(self.features.store.report(7)[0]["paid"], 0)
        self.features.bill_callback(call)
        self.features.bill_callback(call)
        report = self.features.store.report(7)[0]
        self.assertEqual((report["paid"], report["cents"] - report["paid"]), (20, 30))
        entries = self.features.store.payment_history(7)
        self.assertEqual(len(entries), 1)
        self.assertEqual((entries[0]["before_cents"], entries[0]["after_cents"], entries[0]["actor_id"]), (0, 20, "1"))
        self.features.store = ResellerStore(self.features.store.path)
        self.features.store.now = lambda: self.now
        self.features.bill_callback(call)
        self.assertEqual(self.features.store.report(7)[0]["paid"], 20)
        second = self.partial_command("0.30", 501)
        self.features.bill_callback(second)
        self.assertEqual(self.features.store.report(7)[0]["paid"], 50)
        self.assertEqual(len(self.features.store.payment_history(7)), 2)

    def test_partial_stale_confirmation_and_pending_audit(self):
        self.purchase()
        first = self.partial_command("0.20", 500)
        second = self.partial_command("0.30", 501)
        self.features.bill_callback(first)
        self.assertNotIn(501, [c.kwargs["message_id"] for c in self.bot.edit_message_text.call_args_list])
        self.features.bill_callback(second)
        self.assertEqual(self.features.store.report(7)[0]["paid"], 20)
        pending = self.bill_call(first.data.rsplit(":", 1)[0] + ":pending")
        self.features.bill_callback(pending)
        self.assertEqual(self.features.store.report(7)[0]["paid"], 0)
        history = self.features.store.payment_history(7)
        self.assertEqual((history[0]["action"], history[0]["before_cents"], history[0]["after_cents"]), ("pending", 20, 0))

    def test_invalid_partial_amounts_and_owner_only_history(self):
        self.purchase()
        self.message.from_user.id = 1
        for amount in ("0", "-1", "0.001", "nan", "1e2", "0.51"):
            self.message.text = f"/seller paid 7 {amount}"
            self.features.command(self.message)
        self.bot.send_message.assert_not_called()
        self.message.from_user.id = 7
        self.message.text = "/seller payments 7"
        self.features.command(self.message)
        self.assertNotIn("RESELLER PAYMENT HISTORY", self.messages[-1])

    def test_partial_old_date_and_history_output(self):
        self.purchase()
        self.now += timedelta(days=1)
        call = self.partial_command("0.20 2026-09-13")
        self.features.bill_callback(call)
        self.assertEqual(self.features.store.report(7, "2026-09-13")[0]["paid"], 20)
        self.assertEqual(self.features.store.report(7)[0]["paid"], 0)
        self.message.text = "/seller payments 7"
        self.features.command(self.message)
        self.assertIn("PARTIAL", self.messages[-1])
        self.assertIn("$0.00 → $0.20", self.messages[-1])

    def test_concurrent_partial_confirmation_only_adds_once(self):
        self.purchase()
        call = self.partial_command()
        _, bill_id, status = call.data.split(":")
        def confirm():
            try:
                self.features.store.set_bill_status(int(bill_id), status, 1, 500, 1)
                return True
            except SellerError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: confirm(), range(2)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.features.store.report(7)[0]["paid"], 20)
        self.assertEqual(len(self.features.store.payment_history(7)), 1)

    def test_full_payment_and_pending_history_survive_later_charges(self):
        self.purchase()
        bill = self.features.store.manual_bill(7)
        self.features.store.manual_bill_sent(bill["bill_id"], 1, 500)
        self.features.bill_callback(self.bill_call(f"sellerbill:{bill['bill_id']}:paid"))
        self.features.bill_callback(self.bill_call(f"sellerbill:{bill['bill_id']}:pending"))
        entries = self.features.store.payment_history(7)
        self.assertEqual([(e["action"], e["before_cents"], e["after_cents"]) for e in entries], [("pending", 50, 0), ("paid", 0, 50)])
        call = self.partial_command()
        self.purchase("later", 2000)
        self.features.bill_callback(call)
        self.assertEqual(self.features.store.report(7)[0]["paid"], 0)
        self.assertEqual(len(self.features.store.payment_history(7)), 2)

    def test_manual_bill_send_failure_leaves_payment_unchanged(self):
        self.purchase()
        self.message.from_user.id = 1
        self.message.text = "/seller paid 7"
        self.bot.send_message.side_effect = RuntimeError("offline")
        self.features.command(self.message)
        self.assertIn("Payment was not changed", self.messages[-1])
        self.assertEqual(self.features.store.report(7)[0]["paid"], 0)

    def test_old_manual_bill_does_not_trigger_historical_auto_send(self):
        self.now -= timedelta(days=1)
        self.purchase()
        bill = self.features.store.manual_bill(7)
        self.features.store.manual_bill_sent(bill["bill_id"], 1, 499)
        self.now += timedelta(days=1)
        self.features.send_daily_bills()
        self.bot.send_message.assert_not_called()

    def test_bill_callback_on_other_bot_cannot_change_payment(self):
        self.purchase()
        bill = self.features.store.manual_bill(7)
        self.features.store.manual_bill_sent(bill["bill_id"], 1, 500)
        other_bot = Mock()
        self.core.active_bot_for = lambda message: other_bot
        self.features.bill_callback(self.bill_call(f"sellerbill:{bill['bill_id']}:paid"))
        self.assertEqual(self.features.store.report(7)[0]["paid"], 0)
        other_bot.answer_callback_query.assert_called_once()

    def test_reseller_invalid_command_shows_only_reseller_help(self):
        self.message.text = "/seller paid 7"
        self.features.command(self.message)
        self.assertNotIn("/seller paid", self.messages[-1])
        self.assertNotIn("/seller disable", self.messages[-1])
        self.assertIn("/seller history", self.messages[-1])

    def test_manual_payment_at_9pm_and_later_purchases(self):
        self.now = self.now.replace(hour=21)
        self.purchase()
        self.message.from_user.id = 1
        self.message.chat.id = 1
        self.message.text = "/seller paid 7"
        self.features.command(self.message)
        sent = self.bot.send_message.call_args
        self.assertIn("Total: $0.50", sent.args[1])
        self.assertIn("2026-09-13", sent.args[1])
        self.assertEqual(self.features.store.report(7)[0]["paid"], 0)
        button = sent.kwargs["reply_markup"].keyboard[0][0]
        self.features.bill_callback(self.bill_call(button.callback_data))
        self.features.bill_callback(self.bill_call(button.callback_data))
        self.assertEqual(self.features.store.report(7)[0]["paid"], 50)
        self.purchase("later", 2000)
        self.features.bill_callback(self.bill_call(button.callback_data))
        report = self.features.store.report(7)[0]
        self.assertEqual(report["cents"] - report["paid"], 100)
        self.bot.send_message.reset_mock()
        self.features.send_daily_bills()
        self.bot.send_message.assert_not_called()
        self.now = datetime(2026, 9, 14, 3, tzinfo=ICT)
        self.features.send_daily_bills()
        self.assertIn("Due: $1.00", self.bot.send_message.call_args.args[1])

    def test_manual_bill_does_not_replace_end_of_day_bill(self):
        self.purchase()
        bill = self.features.store.manual_bill(7)
        self.features.store.manual_bill_sent(bill["bill_id"], 1, 499)
        self.features.send_daily_bills()
        self.bot.send_message.assert_not_called()
        self.now = datetime(2026, 9, 14, 2, 59, tzinfo=ICT)
        self.assertEqual(self.features.store.manual_bill(7)["day"], "2026-09-13")
        self.now += timedelta(minutes=1)
        self.features.send_daily_bills()
        self.bot.send_message.assert_called_once()

    def test_daily_cutoff_bill_buttons_and_no_resend(self):
        self.purchase()
        self.now = datetime(2026, 9, 14, 2, 59, 59, tzinfo=ICT)
        self.features.send_daily_bills()
        self.bot.send_message.assert_not_called()
        self.now += timedelta(seconds=1)
        self.features.send_daily_bills()
        self.bot.send_message.assert_called_once()
        call = self.bot.send_message.call_args
        self.assertEqual(call.args[0], 1)
        self.assertIn("2026-09-13", call.args[1])
        self.assertIn("Total: $0.50", call.args[1])
        self.assertIn("Dara Sok", call.args[1])
        buttons = call.kwargs["reply_markup"].keyboard[0]
        self.assertEqual([b.text for b in buttons], ["✅ Paid", "⏳ Pending"])
        self.features.send_daily_bills()
        self.bot.send_message.assert_called_once()

    def bill_call(self, data, user_id=1):
        return SimpleNamespace(id="bill-tap", data=data, from_user=SimpleNamespace(id=user_id),
                               message=SimpleNamespace(chat=SimpleNamespace(id=1), message_id=500))

    def test_owner_only_paid_pending_and_date_isolation(self):
        self.purchase()
        self.now += timedelta(days=1)
        self.features.send_daily_bills()
        buttons = self.bot.send_message.call_args.kwargs["reply_markup"].keyboard[0]
        self.purchase("today", 2000)
        self.features.bill_callback(self.bill_call(buttons[0].callback_data, user_id=7))
        self.assertEqual(self.features.store.report(7, "2026-09-13")[0]["paid"], 0)
        self.features.bill_callback(self.bill_call(buttons[0].callback_data))
        self.assertEqual(self.features.store.report(7, "2026-09-13")[0]["paid"], 50)
        self.assertEqual(self.features.store.report(7, "2026-09-14")[0]["paid"], 0)
        self.assertIn("Status: Paid", self.bot.edit_message_text.call_args.kwargs["text"])
        self.features.bill_callback(self.bill_call(buttons[1].callback_data))
        self.assertEqual(self.features.store.report(7, "2026-09-13")[0]["paid"], 0)
        self.assertEqual(self.features.store.report(7)[0]["remaining"], 8)

    def test_unsent_bill_retried_after_restart_and_no_empty_bills(self):
        self.purchase()
        self.now += timedelta(days=2)
        self.bot.send_message.side_effect = RuntimeError("offline")
        self.features.send_daily_bills()
        self.assertEqual(len(self.features.store.pending_daily_bills()), 1)
        restarted = ResellerFeatures(self.core)
        restarted.store.now = lambda: self.now
        self.bot.send_message.side_effect = None
        restarted.send_daily_bills()
        self.assertEqual(restarted.store.pending_daily_bills(), [])
        self.assertEqual(self.features.store.report(7)[0]["remaining"], 9)
        self.assertIn("2026-09-13", self.bot.send_message.call_args.args[1])

    def test_bill_waits_for_inflight_and_rejects_changed_snapshot(self):
        self.purchase()
        self.now = datetime(2026, 9, 14, 2, 59, tzinfo=ICT)
        self.features.store.reserve(7, "pending", "likeff", "123")
        self.now += timedelta(minutes=1)
        self.features.send_daily_bills()
        self.bot.send_message.assert_not_called()
        self.features.store.finish_manual("pending", 220)
        self.features.send_daily_bills()
        buttons = self.bot.send_message.call_args.kwargs["reply_markup"].keyboard[0]
        self.assertIn("Total: $0.70", self.bot.send_message.call_args.args[1])
        # Model a delayed accounting update on that same closed billing day.
        with self.features.store.db() as db:
            db.execute("UPDATE seller_events SET cents=100 WHERE event_id='purchase'")
        self.features.bill_callback(self.bill_call(buttons[0].callback_data))
        self.assertEqual(self.features.store.report(7, "2026-09-13")[0]["paid"], 0)
        self.assertTrue(self.bot.answer_callback_query.call_args.kwargs["show_alert"])
        self.bot.send_message.return_value = SimpleNamespace(message_id=501)
        self.features.send_daily_bills()
        self.assertIn("Total: $1.20", self.bot.send_message.call_args.args[1])

    def test_pending_bill_reminder_after_24_hours_only_once(self):
        self.purchase()
        self.now += timedelta(days=1)
        self.features.send_daily_bills()
        self.bot.send_message.reset_mock()
        self.now += timedelta(hours=23, minutes=59, seconds=59)
        self.features.send_bill_reminders()
        self.bot.send_message.assert_not_called()
        self.now += timedelta(seconds=1)
        self.bot.send_message.return_value = SimpleNamespace(message_id=501)
        self.features.send_bill_reminders()
        self.bot.send_message.assert_called_once()
        call = self.bot.send_message.call_args
        self.assertEqual(call.args[0], 1)
        self.assertIn("RESELLER PAYMENT REMINDER", call.args[1])
        self.assertIn("Due: $0.50", call.args[1])
        self.assertEqual([b.text for b in call.kwargs["reply_markup"].keyboard[0]], ["✅ Paid", "⏳ Pending"])
        self.now += timedelta(days=1)
        restarted = ResellerFeatures(self.core)
        restarted.store.now = lambda: self.now
        restarted.send_bill_reminders()
        self.bot.send_message.assert_called_once()
        self.assertEqual(restarted.store.report(7)[0]["remaining"], 9)

    def test_reminder_paid_button_updates_both_messages(self):
        self.purchase()
        self.now += timedelta(days=1)
        self.features.send_daily_bills()
        self.now += timedelta(hours=24)
        self.bot.send_message.return_value = SimpleNamespace(message_id=501)
        self.features.send_bill_reminders()
        button = self.bot.send_message.call_args.kwargs["reply_markup"].keyboard[0][0]
        call = self.bill_call(button.callback_data)
        call.message.message_id = 501
        self.features.bill_callback(call)
        self.assertEqual(self.features.store.report(7, "2026-09-13")[0]["paid"], 50)
        edits = self.bot.edit_message_text.call_args_list
        self.assertEqual({e.kwargs["message_id"] for e in edits}, {500, 501})
        self.assertTrue(all("Status: Paid" in e.kwargs["text"] for e in edits))

    def test_paid_bill_skipped_and_failed_reminder_retried(self):
        self.purchase()
        self.now += timedelta(days=1)
        self.features.send_daily_bills()
        bill_buttons = self.bot.send_message.call_args.kwargs["reply_markup"].keyboard[0]
        self.features.bill_callback(self.bill_call(bill_buttons[0].callback_data))
        self.now += timedelta(hours=24)
        self.bot.send_message.reset_mock()
        self.features.send_bill_reminders()
        self.bot.send_message.assert_not_called()
        self.features.bill_callback(self.bill_call(bill_buttons[1].callback_data))
        self.bot.send_message.side_effect = RuntimeError("offline")
        self.features.send_bill_reminders()
        self.assertEqual(len(self.features.store.due_bill_reminders()), 1)
        restarted = ResellerFeatures(self.core)
        restarted.store.now = lambda: self.now
        self.bot.send_message.side_effect = None
        self.bot.send_message.return_value = SimpleNamespace(message_id=501)
        restarted.send_bill_reminders()
        self.assertEqual(restarted.store.due_bill_reminders(), [])


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
