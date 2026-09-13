import contextlib
import ast
import importlib.util
import io
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor, Future

from token_refresh_alerts import TokenRefreshAlerts, failure_report, refresh_all, coalesced_refresh


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = TokenRefreshAlerts(str(Path(self.temp.name) / "alerts.sqlite3"))

    def test_exact_compact_report_without_passwords(self):
        report = failure_report("likeff", 4, "noise\n🔄 UID/PASS Token Refresh Report\n🔁 Duplicate skipped: 0\n❌ Failed token: 36\n🆔 Duplicate UID: None\nFailed UID/PASS: SECRET")
        self.assertEqual(report, "⚠️ LIKEFF SLOT 4 TOKEN REFRESH FAILED\n━━━━━━━━━━━━━━━━━━\n🔄 UID/PASS Token Refresh Report\n\n🔁 Duplicate skipped: 0\n❌ Failed token: 36\n🆔 Duplicate UID: None")

    def test_interrupted_progress_keeps_known_failures_separate(self):
        output = 'REFRESH_PROGRESS {"refreshed": 180, "failed": 12, "unfinished": 28, "duplicates": 0, "duplicate_uids": []}\n'
        report = failure_report("likeff", 1, output)
        self.assertIn("Failed token: 12", report)
        self.assertIn("Unfinished: 28", report)
        self.assertNotIn("Unknown", report)
        refresh_all([("likeff", 1)], lambda *a: (1, output), self.queue, Mock())
        bot = Mock()
        self.queue.send_pending(bot, 1, Mock())
        summary = bot.send_message.call_args.args[1]
        self.assertIn("Failed tokens: 12", summary)
        self.assertIn("Unfinished accounts: 28", summary)
        self.assertNotIn("slots unknown", summary)

    def test_each_failed_slot_and_crash_queued_success_skipped(self):
        def refresh(name, slot):
            if slot == 1:
                raise subprocess.TimeoutExpired("secret-command", 900)
            return (1, "Failed token: 2") if slot == 2 else (0, "")
        refresh_all([("likeff", n) for n in (1, 2, 3)], refresh, self.queue, Mock())
        bot = Mock()
        self.queue.send_pending(bot, 1, Mock())
        self.assertEqual(bot.send_message.call_count, 3)
        texts = [c.args[1] for c in bot.send_message.call_args_list]
        self.assertTrue(any("SLOT 1" in t and "Unknown" in t for t in texts))
        self.assertTrue(any("SLOT 2" in t and "Failed token: 2" in t for t in texts))
        self.assertTrue(all("secret-command" not in t for t in texts))

    def test_alert_delivery_retry_survives_restart(self):
        self.queue.enqueue("alert")
        bot = Mock()
        bot.send_message.side_effect = RuntimeError("offline")
        self.queue.send_pending(bot, 1, Mock())
        bot.send_message.side_effect = None
        restarted = TokenRefreshAlerts(self.queue.path)
        restarted.send_pending(bot, 1, Mock())
        restarted.send_pending(bot, 1, Mock())
        self.assertEqual(bot.send_message.call_count, 2)

    def test_bot_refresh_timeout_and_manual_failure_queue_once(self):
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_token_update")
        import os
        runner = Mock()
        ns = dict(sys=sys, os=os, re=re, logger=Mock(), BASE_DIR=self.temp.name, subprocess=SimpleNamespace(run=runner), token_refresh_alerts=self.queue, failure_report=failure_report, coalesced_refresh=coalesced_refresh)
        exec(compile(ast.Module(body=[node], type_ignores=[]), "telegram_bot.py", "exec"), ns)
        runner.side_effect = subprocess.TimeoutExpired("refresh", 900, output=b'REFRESH_PROGRESS {"refreshed": 10, "failed": 2, "unfinished": 208}\n')
        self.assertEqual(ns["run_token_update"]("likeff", 4)[0], 1)
        runner.side_effect = None
        runner.return_value = SimpleNamespace(returncode=1, stdout="Failed token: 36", stderr="")
        refresh_all([("likeff", 5)], ns["run_token_update"], self.queue, Mock(), report_failures=False)
        bot = Mock()
        self.queue.send_pending(bot, 1, Mock())
        self.assertEqual(bot.send_message.call_count, 3)
        self.assertIn("Failed token: 2", bot.send_message.call_args_list[0].args[1])
        self.assertIn("Unfinished: 208", bot.send_message.call_args_list[0].args[1])
        self.assertTrue(any("SLOT 5" in c.args[1] for c in bot.send_message.call_args_list))

    def test_existing_token_slot_without_credentials_is_not_silently_skipped(self):
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "token_refresh_targets")
        ns = dict(LIKEFF_SLOT_COUNT=3, os=SimpleNamespace(path=SimpleNamespace(exists=lambda path: path in ("uid1", "token2"))), uidpass_path_for=lambda name, slot: f"uid{slot}", token_path_for=lambda name, slot: f"token{slot}")
        exec(compile(ast.Module(body=[node], type_ignores=[]), "telegram_bot.py", "exec"), ns)
        self.assertEqual(ns["token_refresh_targets"](), [("like", None), ("likeff", 1), ("likeff", 2)])

    def load_updater(self):
        spec = importlib.util.spec_from_file_location("isolated_token_updater", "update_like_tokens.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"lssj": SimpleNamespace()}):
            spec.loader.exec_module(module)
        module.FILE_SETS = {"like": (str(Path(self.temp.name) / "accounts.json"), str(Path(self.temp.name) / "tokens.json"))}
        return module

    def test_accounts_parallel_deduplicated_and_failures_counted(self):
        module = self.load_updater()
        accounts = [{"uid": str(i), "password": "secret"} for i in range(1, 5)]
        accounts += [{"uid": "1", "password": "secret"}, None]
        Path(module.FILE_SETS["like"][0]).write_text(json.dumps(accounts))
        barrier = threading.Barrier(4)
        def fetch(uid, password):
            barrier.wait(timeout=5)
            if uid == "4":
                raise RuntimeError("secret")
            return {"uid": uid, "token": "fake"}
        out = io.StringIO()
        with patch.object(module, "fetch_jwt", side_effect=fetch), patch.object(sys, "argv", ["update", "like"]), contextlib.redirect_stdout(out):
            self.assertEqual(module.main(), 1)
        self.assertIn("Failed token: 2", out.getvalue())
        self.assertIn("Duplicate skipped: 1", out.getvalue())
        self.assertNotIn("secret", out.getvalue())
        self.assertEqual(len(json.loads(Path(module.FILE_SETS["like"][1]).read_text())), 3)

    def test_total_failure_preserves_existing_tokens(self):
        module = self.load_updater()
        accounts, tokens = map(Path, module.FILE_SETS["like"])
        accounts.write_text('[{"uid":"1","password":"secret"}]')
        tokens.write_text('[{"uid":"1","token":"old"}]')
        with patch.object(module, "fetch_jwt", side_effect=RuntimeError()), patch.object(sys, "argv", ["update", "like"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 1)
        self.assertEqual(json.loads(tokens.read_text())[0]["token"], "old")

    def test_partial_success_keeps_failed_account_and_checkpoints(self):
        module = self.load_updater()
        accounts, tokens = map(Path, module.FILE_SETS["like"])
        accounts.write_text('[{"uid":"1","password":"secret"},{"uid":"2","password":"secret"}]')
        tokens.write_text('[{"uid":"2","token":"old"},{"uid":"removed","token":"old"}]')
        def fetch(uid, password):
            if uid == "2":
                raise RuntimeError()
            return {"uid": uid, "token": "new"}
        with patch.object(module, "fetch_jwt", side_effect=fetch), patch.object(module, "update_token_file", wraps=module.update_token_file) as write, patch.object(sys, "argv", ["update", "like"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 1)
        self.assertEqual(write.call_count, 2)  # checkpoint and final save
        self.assertEqual({x["uid"]: x["token"] for x in json.loads(tokens.read_text())}, {"1": "new", "2": "old"})

    def test_failed_atomic_replace_preserves_file(self):
        module = self.load_updater()
        target = Path(module.FILE_SETS["like"][1])
        target.write_text("[]")
        with patch.object(module.os, "replace", side_effect=OSError("blocked")):
            with self.assertRaises(OSError):
                module.update_token_file([{"token": "new"}], str(target))
        self.assertEqual(target.read_text(), "[]")
        self.assertEqual(list(Path(self.temp.name).iterdir()), [target])

    def test_windows_file_lock_retried(self):
        module = self.load_updater()
        target = Path(module.FILE_SETS["like"][1])
        target.write_text("[]")
        replace = module.os.replace
        attempts = []
        def locked_then_available(source, destination):
            attempts.append(1)
            if len(attempts) < 3:
                raise PermissionError("File temporarily open")
            return replace(source, destination)
        with patch.object(module.os, "replace", side_effect=locked_then_available), patch.object(module.time, "sleep"):
            module.update_token_file([{"uid": "1", "token": "new"}], str(target))
        self.assertEqual(len(attempts), 3)
        self.assertEqual(json.loads(target.read_text())[0]["token"], "new")

    def test_220_accounts_refresh_with_batched_writes(self):
        module = self.load_updater()
        accounts, tokens = map(Path, module.FILE_SETS["like"])
        accounts.write_text(json.dumps([{"uid": str(i), "password": "fake"} for i in range(1, 221)]))
        out = io.StringIO()
        with patch.object(module, "fetch_jwt", side_effect=lambda uid, password: {"uid": uid, "token": "fake"}) as fetch, patch.object(module, "update_token_file", wraps=module.update_token_file) as write, patch.object(sys, "argv", ["update", "like"]), contextlib.redirect_stdout(out):
            self.assertEqual(module.main(), 0)
        self.assertEqual(fetch.call_count, 220)
        self.assertEqual(write.call_count, 13)
        self.assertEqual(len(json.loads(tokens.read_text())), 220)
        self.assertIn('"refreshed": 220, "failed": 0', out.getvalue())

    def test_refresh_uses_isolated_session_and_three_attempts(self):
        module = self.load_updater()
        module.lssj.fetch_guest_jwt_for_like_with_retry = Mock(return_value={"token": "fake"})
        with patch.object(module.requests, "Session") as session:
            self.assertEqual(module.fetch_jwt("1", "secret"), {"token": "fake"})
            module.lssj.fetch_guest_jwt_for_like_with_retry.assert_called_once_with("1", "secret", max_retries=1, session=session.return_value.__enter__.return_value)

    def test_retry_backoff_stops_after_success(self):
        module = self.load_updater()
        fetch = module.lssj.fetch_guest_jwt_for_like_with_retry = Mock(side_effect=[RuntimeError(), {"token": "ok"}])
        with patch.object(module.requests, "Session"), patch.object(module.time, "sleep") as sleep:
            self.assertEqual(module.fetch_jwt("1", "secret"), {"token": "ok"})
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_three_slots_parallel_and_summary_counts(self):
        barrier = threading.Barrier(3)
        def refresh(name, slot):
            barrier.wait(timeout=5)
            return (int(slot == 2), 'REFRESH_STATS {"refreshed": 10, "failed": ' + str(int(slot == 2)) + '}')
        refresh_all([("likeff", i) for i in (1, 2, 3)], refresh, self.queue, Mock())
        bot = Mock()
        self.queue.send_pending(bot, 1, Mock())
        summary = bot.send_message.call_args.args[1]
        for text in ("Slots checked: 3", "Successful slots: 2", "Slots with failures: 1", "Tokens refreshed: 30", "Failed tokens: 1"):
            self.assertIn(text, summary)

    def test_overlapping_refreshes_share_result(self):
        started, waiting, release = threading.Event(), threading.Event(), threading.Event()
        class ObservedFuture(Future):
            def result(self, *args, **kwargs):
                waiting.set()
                return super().result(*args, **kwargs)
        refresh = Mock()
        def work(name, slot):
            refresh(name, slot)
            started.set()
            if not release.wait(5):
                raise AssertionError("Refresh did not release")
            return 0, "done"
        wrapped = coalesced_refresh(work)
        with patch("token_refresh_alerts.Future", ObservedFuture), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(wrapped, "likeff", 1)
            try:
                self.assertTrue(started.wait(5))
                second = pool.submit(wrapped, "likeff", 1)
                self.assertTrue(waiting.wait(5))
            finally:
                release.set()
            self.assertEqual(first.result(), second.result())
        refresh.assert_called_once()
        self.assertEqual(wrapped("likeff", 1), (0, "done"))
        self.assertEqual(refresh.call_count, 2)


if __name__ == "__main__":
    unittest.main()
