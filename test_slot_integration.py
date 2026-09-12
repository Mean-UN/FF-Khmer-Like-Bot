"""Offline integration checks; no real likes or Telegram messages are sent."""
import ast
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import lssj
from request_usage import ICT, SlotUsage


class SlotIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tracker = SlotUsage(os.path.join(self.temp.name, "usage.db"))
        self.original = lssj.app.extensions["slot_usage"]
        lssj.app.extensions["slot_usage"] = self.tracker
        self.addCleanup(lambda: lssj.app.extensions.__setitem__("slot_usage", self.original))
        self.delta = 100
        self.reads = 0
        self.slots = {1, 3}
        async def info(*args):
            self.reads += 1
            return {"AccountInfo": {"UID": "123", "Likes": 10 if self.reads % 2 else 10 + self.delta}}
        async def send(*args, **kwargs):
            return [200]
        for name, kwargs in [
            ("get_cached_region", {"return_value": "SG"}),
            ("load_like_tokens", {"side_effect": lambda **kw: ["fake"] if kw.get("slot") in self.slots or kw.get("slot") is None else []}),
            ("fetch_like_info_with_tokens", {"side_effect": info}),
            ("send_like_requests", {"side_effect": send}),
        ]:
            patcher = patch.object(lssj, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        source = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        names = {"process_like", "deliver_autolike_order", "autolike_order_status"}
        nodes = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
        for node in nodes:
            node.decorator_list = []
        self.bot = Mock()
        self.ns = dict(datetime=datetime, timedelta=timedelta, CAMBODIA_TZ=ICT,
            is_owner=lambda uid: True,
            usage_tracker={}, usage_reset_period=lambda now: now.date(),
            get_user_limit=lambda uid: 100, resolve_like_region=lambda *a: ("SG", "cache"),
            call_api=self.api, owner_contact_text=lambda: "Owner",
            remember_like_success=Mock(), format_next_like_wait=lambda *a: "Tomorrow",
            current_autolike_period=lambda now: now.date().isoformat(),
            notify_autolike_order=Mock(), format_autolike_delivery=lambda *a, **kw: "Delivery",
            logger=Mock(), run_token_update=Mock(), get_likeff_assigned_slot=lambda uid: None)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "telegram_bot.py", "exec"), self.ns)

    def api(self, endpoint, params, **kwargs):
        with lssj.app.test_client() as client:
            return client.get("/" + endpoint, query_string=params).json

    def manual(self):
        message = SimpleNamespace(from_user=SimpleNamespace(id=7))
        self.ns["process_like"](message, "likeff", "123", active_bot=self.bot)

    def auto(self):
        order = {"uid": "123", "sent_likes": 0, "total_likes": 1000, "status": "active"}
        result = self.ns["deliver_autolike_order"](order, notify_failure=False)
        return result, order

    def test_manual_and_auto_share_success_counts(self):
        self.manual()
        result, order = self.auto()
        self.assertTrue(result)
        self.assertEqual(order["sent_likes"], 100)
        self.assertEqual(self.tracker.snapshot(1)["used"], 2)
        self.assertEqual(self.ns["usage_tracker"][7]["used"], 1)

    def test_zero_likes_preserves_last_request(self):
        for _ in range(29):
            self.tracker.finish(self.tracker.reserve([1]), 1)
        self.delta = 0
        self.manual()
        _, order = self.auto()
        self.assertEqual(order["sent_likes"], 0)
        self.assertEqual(self.tracker.snapshot(1)["remaining"], 1)
        self.delta = 100
        self.manual()
        self.assertEqual(self.tracker.snapshot(1)["used"], 30)
        self.auto()
        self.assertEqual(self.tracker.snapshot(3)["used"], 1)
        self.assertEqual(self.tracker.snapshot(2)["used"], 0)

    def test_auth_failure_identifies_slot_and_releases_capacity(self):
        with patch.object(lssj, "fetch_like_info_with_tokens", side_effect=RuntimeError("401 Unauthorized")):
            result, order = self.auto()
        self.assertFalse(result)
        self.ns["run_token_update"].assert_called_once_with("likeff", 1)
        self.assertIn("401", order["last_error"])
        self.assertEqual(self.tracker.snapshot(1)["used"], 0)
        with self.tracker.database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM slot_pending").fetchone()[0], 0)

    def test_exhaustion_does_not_send(self):
        self.slots = {1}
        for _ in range(30):
            self.tracker.finish(self.tracker.reserve([1]), 1)
        result, order = self.auto()
        self.assertFalse(result)
        self.assertIn("full", order["last_error"])
        lssj.send_like_requests.assert_not_called()

    def test_other_api_does_not_consume_slot(self):
        self.api("like", {"uid": "123"})
        self.assertEqual(self.tracker.snapshot(1)["used"], 0)

    def test_concurrent_reservations_and_reset(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            reservations = list(pool.map(lambda _: self.tracker.reserve([1, 3]), range(35)))
        self.assertEqual(sum(r[2] == 1 for r in reservations), 30)
        for r in reservations:
            self.tracker.finish(r, 1)
        with patch("request_usage.datetime") as clock:
            clock.now.return_value = datetime(2026, 9, 13, 2, 59, 59, tzinfo=ICT)
            self.assertEqual(self.tracker.today(), "2026-09-12")
            clock.now.return_value = datetime(2026, 9, 13, 3, 0, tzinfo=ICT)
            self.assertEqual(self.tracker.today(), "2026-09-13")
        other = SlotUsage(self.tracker.path)
        self.assertEqual(other.snapshot(1)["used"], 30)


if __name__ == "__main__":
    unittest.main()
