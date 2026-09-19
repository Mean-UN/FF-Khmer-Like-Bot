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
        sleep_patch = patch("time.sleep")
        sleep_patch.start()
        self.addCleanup(sleep_patch.stop)
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
        sleep.assert_called_once()
        self.assertGreaterEqual(sleep.call_args.args[0], 2)
        self.assertLessEqual(sleep.call_args.args[0], 3)

    def test_recovery_pass_only_retries_failed_accounts(self):
        module = self.load_updater()
        accounts, tokens = map(Path, module.FILE_SETS["like"])
        accounts.write_text(json.dumps([{"uid": str(i), "password": "fake"} for i in (1, 2)]))
        attempts = {}
        def fetch(uid, password):
            attempts[uid] = attempts.get(uid, 0) + 1
            if uid == "2" and attempts[uid] == 1:
                raise RuntimeError("temporary")
            return {"uid": uid, "token": "fake"}
        out = io.StringIO()
        with patch.object(module, "fetch_jwt", side_effect=fetch), patch.object(sys, "argv", ["update", "like"]), contextlib.redirect_stdout(out):
            self.assertEqual(module.main(), 0)
        self.assertEqual(attempts, {"1": 1, "2": 2})
        self.assertEqual(len(json.loads(tokens.read_text())), 2)
        self.assertIn('"refreshed": 2, "failed": 0', out.getvalue())

    def test_rate_limit_retry_after_is_respected(self):
        module = self.load_updater()
        response = SimpleNamespace(status_code=429, headers={"Retry-After": "20"})
        error = module.requests.HTTPError("rate limited", response=response)
        module.lssj.fetch_guest_jwt_for_like_with_retry = Mock(side_effect=[error, {"token": "ok"}])
        with patch.object(module.requests, "Session"), patch.object(module.time, "sleep") as sleep:
            module.fetch_jwt("1", "fake")
        self.assertGreaterEqual(sleep.call_args.args[0], 20)
        self.assertLessEqual(sleep.call_args.args[0], 21)

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


class GuestGenerationTests(unittest.TestCase):
    def setUp(self):
        import requests
        import hashlib
        import hmac
        import guest_protocol
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        from google.protobuf import message
        from urllib.parse import urlparse
        self.requests = requests
        tree = ast.parse(Path("lssj.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create_guest_account_with_proxy")
        self.session = Mock()
        context = Mock()
        context.__enter__ = Mock(return_value=self.session)
        context.__exit__ = Mock(return_value=False)
        self.ns = dict(guest_registration=SimpleNamespace(REGISTRATION_GATE=SimpleNamespace(post=lambda session, url, **kwargs: session.post(url, **kwargs))), jwt_protocol=SimpleNamespace(RELEASE_VERSION="OB55", parse_login_response=Mock(return_value={"token":"fake-jwt", "account_id":"123", "lock_region":"ME"})), guest_protocol=guest_protocol, AES=AES, unpad=unpad, message=message, json=json, hashlib=hashlib, hmac=hmac, requests=SimpleNamespace(Session=Mock(return_value=context), RequestException=requests.RequestException),
                       generate_custom_password=Mock(return_value="original-password"),
                       generate_random_name=Mock(return_value="original-name"), normalize_region=lambda r: r.upper(),
                       is_region_match=lambda a, b: a == b,
                       urlparse=urlparse, USERAGENT="agent", with_region_ip_headers=lambda h, r: h,
                       response_json_or_text=lambda response: response.json(), CLIENT_SECRET="fake", CLIENT_ID="100067",
                       REGION_LANG={"ME": "en"}, build_proto=Mock(return_value=b"payload"),
                       major_register_url=lambda *a: "https://example.test/MajorRegister",
                       major_login_url=lambda *a: "https://example.test/MajorLogin",
                       BmwNoiNoiBmvYasYas=lambda g, f, data: data, G="", F="",
                       build_major_login_request=Mock(return_value=SimpleNamespace(SerializeToString=lambda: b"login")),
                       MajorLoginRes_pb2=SimpleNamespace(MajorLoginRes=Mock(return_value=Mock())),
                       MessageToDict=lambda *a, **kw: {"token": "fake-jwt", "account_id": "123", "lock_region": "ME"},
                       decode_jwt_payload=lambda token: {}, time=SimpleNamespace(sleep=Mock(), time=lambda: 1800000000))
        exec(compile(ast.Module(body=[node], type_ignores=[]), "lssj.py", "exec"), self.ns)

    def response(self, data=None, status=200):
        result = Mock(status_code=status, content=b"protobuf")
        result.json.return_value = data
        if status >= 400:
            result.raise_for_status.side_effect = self.requests.HTTPError(response=result)
        return result

    def run_guest(self, ghost=False):
        return self.ns["create_guest_account_with_proxy"]("ME", "base", "prefix", ghost, "http://proxy.test")

    def test_preserves_name_password_and_checks_new_register_fields(self):
        self.session.post.side_effect = [self.response({"code": 0, "data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"}), self.response(), self.response()]
        result = self.run_guest(True)
        self.assertTrue(result["major_login_success"])
        self.assertEqual((result["name"], result["password"]), ("original-name", "original-password"))
        self.ns["generate_custom_password"].assert_called_once_with("prefix")
        self.ns["generate_random_name"].assert_called_once_with("base")
        fields = self.ns["build_proto"].call_args_list[0].args[0]
        self.assertEqual((fields[1], fields[15], fields[16], fields[20]), ("original-name", "pt", 2, "1.132.1"))
        self.session.proxies.update.assert_called_once()
        login_fields = self.ns["build_proto"].call_args_list[1].args[0]
        self.assertEqual((login_fields[7], login_fields[22], login_fields[26], login_fields[29]), ("1.132.3", "open", "BR", "access"))

    def test_normal_register_uses_reference_fields_and_matching_host(self):
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"}), self.response(), self.response()]
        result = self.run_guest()
        self.assertTrue(result["success"])
        fields = self.ns["build_proto"].call_args_list[0].args[0]
        self.assertEqual((fields[16], fields[17]), (1, 1))
        self.assertNotIn(20, fields)
        for call in self.session.post.call_args_list[2:]:
            headers = call.kwargs["headers"]
            self.assertEqual(headers["Host"], "example.test")
            self.assertEqual(headers["Authorization"], "Bearer")
            self.assertEqual(headers["X-Unity-Version"], "2018.4.12f1")
            self.assertEqual(headers["X-GA-SV"], "1800000000")

    def test_parse_failure_is_reported_without_losing_credentials(self):
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"}), self.response(), self.response()]
        self.ns["jwt_protocol"].parse_login_response.side_effect = ValueError("invalid login")
        result = self.run_guest()
        self.assertFalse(result["success"])
        self.assertTrue(result["guest_created"])
        self.assertEqual(result["uid"], "7")
        self.assertEqual(result["failed_stage"], "MajorLogin")

    def test_missing_token_fields_uses_fallback_endpoint(self):
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({}), self.response({"data": {"access_token": "access", "open_id": "open"}}), self.response(), self.response()]
        self.assertTrue(self.run_guest()["major_login_success"])
        self.assertIn("token:grant", self.session.post.call_args_list[2].args[0])

    def test_registration_signature_matches_exact_sent_body(self):
        import hashlib
        import hmac
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"}), self.response(), self.response()]
        self.assertTrue(self.run_guest()["major_login_success"])
        request = self.session.post.call_args_list[0].kwargs
        expected_body = b'{"app_id":100067,"client_type":2,"password":"original-password","source":2}'
        self.assertEqual(request["data"], expected_body)
        self.assertNotIn("json", request)
        expected_signature = hmac.new(b"fake", expected_body, hashlib.sha256).hexdigest()
        self.assertEqual(request["headers"]["Authorization"], "Signature " + expected_signature)

    def test_reference_region_routes(self):
        import guest_protocol
        import lssj
        self.assertEqual(lssj.major_register_url("SG"), "https://loginbp.ppmainecoonghj.com/MajorRegister")
        self.assertEqual(lssj.major_register_url("SG", True), "https://loginbp.ggblueshark.com/MajorRegister")
        self.assertEqual(guest_protocol.region_host("SG"), "loginbp.ggpolarbear.com")
        self.assertEqual(guest_protocol.region_host("ME"), "loginbp.common.ggbluefox.com")
        self.assertEqual(guest_protocol.region_host("BR"), "loginbp.ggblueshark.com")
        self.assertEqual(guest_protocol.region_host("SG", True), "loginbp.ggblueshark.com")

    def test_encrypted_login_and_external_id_fallback(self):
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        self.ns["G"], self.ns["F"] = b"a" * 16, b"b" * 16
        plaintext = b"simulated-protobuf"
        response = self.response()
        response.content = AES.new(self.ns["G"], AES.MODE_CBC, self.ns["F"]).encrypt(pad(plaintext, 16))
        self.ns["jwt_protocol"].parse_login_response.return_value = {"token": "fake-jwt", "lock_region":"ME"}
        self.ns["decode_jwt_payload"] = lambda token: {"external_id": "123"}
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"}), self.response(), response]
        result = self.run_guest()
        self.assertTrue(result["major_login_success"])
        self.assertEqual(result["account_id"], "123")
        self.ns["jwt_protocol"].parse_login_response.assert_called_once_with(response.content)

    def test_major_register_failure_keeps_credentials_and_stops_login(self):
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"}), self.response(status=500)]
        result = self.run_guest()
        self.assertEqual(result["failed_stage"], "MajorRegister")
        self.assertEqual(result["uid"], "7")
        self.assertEqual(result["password"], "original-password")
        self.assertFalse(result["major_login_success"])
        self.assertEqual(self.session.post.call_count, 3)

    def test_http_200_registration_error_exposes_safe_upstream_reason(self):
        self.session.post.side_effect = [self.response({"code": 1001, "message": "Rejected original-password", "data": {}})]
        result = self.run_guest()
        self.assertFalse(result["success"])
        self.assertEqual(result["failed_stage"], "Guest register")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["upstream_error"]["code"], "1001")
        self.assertEqual(result["upstream_error"]["message"], "Rejected [redacted]")
        self.assertEqual(self.session.post.call_count, 1)

    def test_http_registration_rejection_is_not_retried(self):
        self.session.post.side_effect = [self.response({"message": "registration denied"}, status=403)]
        result = self.run_guest()
        self.assertEqual(result["http_status"], 403)
        self.assertEqual(result["upstream_error"]["message"], "registration denied")
        self.assertEqual(self.session.post.call_count, 1)

    def test_registration_timeout_does_not_repeat_registration_in_session(self):
        self.session.post.side_effect = self.requests.Timeout()
        result = self.run_guest()
        self.assertFalse(result["guest_created"])
        self.assertEqual(result["failed_stage"], "Guest register")
        self.assertEqual(self.session.post.call_count, 1)

    def test_missing_region_triggers_selection_and_final_login(self):
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"})] + [self.response() for _ in range(5)]
        self.ns["jwt_protocol"].parse_login_response.side_effect = [
            {"token": "initial-jwt", "account_id": "123"},
            {"token": "final-jwt", "account_id": "123", "lock_region": "ME"}]
        result = self.run_guest()
        self.assertTrue(result["success"])
        self.assertEqual(result["jwt_token"], "final-jwt")
        self.assertEqual(result["region"], "ME")
        self.assertTrue(self.session.post.call_args_list[4].args[0].endswith('/ChooseNewbieChoice'))
        self.assertTrue(self.session.post.call_args_list[5].args[0].endswith('/ChooseRegion'))
        self.assertEqual(self.ns["build_proto"].call_args_list[3].args[0], {1: "ME", 2: 1})
        self.assertEqual(self.session.post.call_args_list[5].kwargs['headers']['Authorization'], 'Bearer initial-jwt')

    def test_region_selection_failure_preserves_guest_credentials(self):
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"}), self.response(), self.response(), self.response(), self.response(status=403)]
        self.ns["jwt_protocol"].parse_login_response.return_value = {"token": "fake-jwt", "account_id": "123"}
        result = self.run_guest()
        self.assertFalse(result["success"])
        self.assertTrue(result["guest_created"])
        self.assertEqual(result["password"], "original-password")
        self.assertEqual(result["failed_stage"], "ChooseRegion")
        self.assertEqual(result["http_status"], 403)
        self.assertEqual(self.session.post.call_count, 6)

    def test_final_login_must_confirm_region(self):
        self.session.post.side_effect = [self.response({"data": {"uid": "7"}}), self.response({"access_token": "access", "open_id": "open"})] + [self.response() for _ in range(5)]
        self.ns["jwt_protocol"].parse_login_response.return_value = {"token": "fake-jwt", "account_id": "123"}
        result = self.run_guest()
        self.assertFalse(result["success"])
        self.assertEqual(result["failed_stage"], "MajorLogin after ChooseRegion")
        self.assertIn('confirm the requested region', result['error_detail'])

    def test_region_mismatch_keeps_credentials_without_creating_another_account(self):
        import lssj
        created = {"success": True, "guest_created": True, "region": "BR", "uid": "7", "password": "saved-password"}
        with patch.object(lssj, "get_region_proxy_candidates", return_value=[None]), patch.object(lssj, "create_guest_account_with_proxy", return_value=created) as create:
            result = lssj.create_guest_account("SG", "base", "prefix")
        self.assertFalse(result["success"])
        self.assertEqual(result["password"], "saved-password")
        self.assertEqual(result["failed_stage"], "Region validation")
        create.assert_called_once()


class GuestActivationTests(unittest.TestCase):
    def setUp(self):
        import guest_activation
        self.module = guest_activation
        self.session = Mock()
        self.context = patch.object(guest_activation.requests, "Session")
        self.context.start().return_value.__enter__.return_value = self.session
        self.addCleanup(self.context.stop)

    def response(self, content=b"", data=None):
        result = Mock(status_code=200, content=content)
        result.json.return_value = data
        return result

    def configure(self, server="https://client.ind.freefiremobile.com", login_data=b"\x08\x01"):
        login = bytes(self.module.create_proto({8: "fake-jwt", 10: server}))
        self.session.post.side_effect = [self.response(data={"access_token": "access", "open_id": "open", "platform": 4}), self.response(login), self.response(login_data)]

    def test_activation_requires_all_three_steps(self):
        self.configure()
        result = self.module.activate_guest("123", "secret")
        self.assertTrue(result["success"])
        self.assertEqual(self.session.post.call_count, 3)
        call = self.session.post.call_args
        self.assertEqual(call.args[0], "https://client.ind.freefiremobile.com/GetLoginData")
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer fake-jwt")
        self.assertNotIn("Host", call.kwargs["headers"])
        self.assertNotIn("secret", str(result))

    def test_current_login_payload_types(self):
        plain = self.module.unpad(self.module.AES.new(self.module.aes_key, self.module.AES.MODE_CBC, self.module.aes_iv).decrypt(self.module.major_login_payload("access", "open", 4, "SG")), 16)
        fields = self.module.decode_protobuf(plain)
        self.assertEqual(fields[7], b"1.132.3")
        self.assertEqual(fields[23], b"4")
        self.assertEqual(fields[25], b"realme RMX2189")
        self.assertEqual(fields[26], b"SG")
        self.assertEqual(fields[99], b"4")
        self.assertEqual(fields[100], b"4")

    def test_major_login_value_error_retries_same_account_five_times(self):
        failure = {"success": False, "error": "MajorLogin failed (ValueError)", "retryable": True}
        with patch.object(self.module, "_activate_guest_once", return_value=failure) as once, patch.object(self.module.time, "sleep") as sleep:
            self.assertFalse(self.module.activate_guest("123", "secret", "SG")["success"])
        self.assertEqual(once.call_count, 5)
        self.assertTrue(all(c.args == ("123", "secret", "SG") for c in once.call_args_list))
        self.assertEqual(sleep.call_count, 4)

    def test_retry_stops_on_success(self):
        with patch.object(self.module, "_activate_guest_once", side_effect=[{"success": False, "retryable": True}, {"success": True}]) as once, patch.object(self.module.time, "sleep"):
            self.assertTrue(self.module.activate_guest("123", "secret")["success"])
        self.assertEqual(once.call_count, 2)

    def test_encrypted_login_and_region_host(self):
        self.configure()
        responses = list(self.session.post.side_effect)
        responses[1].content = self.module.AES.new(self.module.aes_key, self.module.AES.MODE_CBC, self.module.aes_iv).encrypt(self.module.pad(responses[1].content, 16))
        self.session.post.side_effect = responses
        self.assertTrue(self.module.activate_guest("123", "secret", "ME")["success"])
        self.assertEqual(self.session.post.call_args_list[1].args[0], "https://loginbp.ppmainecoonghj.com/MajorLogin")

    def test_no_login_data_is_not_success(self):
        self.configure(login_data=b"")
        self.assertFalse(self.module.activate_guest("123", "secret")["success"])

    def test_untrusted_server_never_receives_token(self):
        self.configure(server="https://example.org")
        self.assertFalse(self.module.activate_guest("123", "secret")["success"])
        self.assertEqual(self.session.post.call_count, 2)

    def test_json_formats_and_duplicates(self):
        account = {"uid": "123", "password": "secret"}
        for data in ([account], {"accounts": [account]}, {"one": account}, account):
            self.assertEqual(self.module.parse_accounts(json.dumps(data)), [account])
        with self.assertRaises(ValueError):
            self.module.parse_accounts(json.dumps([account, account]))
        with self.assertRaises(ValueError):
            self.module.decode_protobuf(b"\x42\x10short")

    def test_guestgen_file_format_can_be_activated(self):
        data = {"accounts": 1, "items": [{"uid": "123", "password": "secret", "activated": False}]}
        self.assertEqual(self.module.parse_accounts(json.dumps(data)), [{"uid": "123", "password": "secret"}])

    def test_guestgen_activates_created_account_without_replacing_on_failure(self):
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        names = ("guest_account_record", "generate_and_activate_guest")
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        api = Mock(return_value={"account_id": "456", "uid": "123", "password": "secret", "name": "original"})
        activate = Mock(side_effect=RuntimeError("offline"))
        ns = dict(call_api=api, activate_guest=activate)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "telegram_bot.py", "exec"), ns)
        account, error = ns["generate_and_activate_guest"]("SG", "name")
        self.assertIsNone(error)
        self.assertEqual(account["uid"], "123")
        self.assertFalse(account["activated"])
        api.assert_called_once()
        activate.assert_called_once_with("123", "secret", region="SG")

    def test_guestgen_replaces_missing_account_id(self):
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("guest_account_record", "generate_and_activate_guest")]
        invalid = {"uid": "123", "password": "secret", "account_id": None}
        valid = {"uid": "124", "password": "secret", "account_id": "456"}
        api = Mock(side_effect=[invalid, valid])
        activate = Mock(return_value={"success": True})
        ns = dict(call_api=api, activate_guest=activate)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "telegram_bot.py", "exec"), ns)
        progress = Mock()
        record, error = ns["generate_and_activate_guest"]("SG", "name", progress)
        self.assertEqual(record["uid"], "124")
        self.assertIsNone(error)
        activate.assert_called_once_with("124", "secret", region="SG")
        self.assertEqual([c.args[0] for c in progress.call_args_list], ["created", "activated"])
        api.side_effect = None
        api.return_value = invalid
        activate.reset_mock()
        record, error = ns["generate_and_activate_guest"]("SG", "name")
        self.assertIsNone(record)
        self.assertIn("5 attempts", error)
        activate.assert_not_called()

    def test_bulk_guestgen_three_workers_and_memory_output(self):
        from concurrent.futures import as_completed
        import time
        from datetime import datetime
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_guestgen")
        barrier = threading.Barrier(3)
        def generate(region, name, progress):
            barrier.wait(timeout=5)
            progress("created")
            progress("activated")
            return {"uid": "123", "password": "secret", "activated": True}, None
        bot = Mock()
        bot.send_message.return_value = SimpleNamespace(chat=SimpleNamespace(id=1), message_id=2)
        documents = []
        bot.send_document.side_effect = lambda chat, document, **kwargs: documents.append(json.loads(document.read()))
        ns = dict(bot=bot, ThreadPoolExecutor=ThreadPoolExecutor, as_completed=as_completed, generate_and_activate_guest=generate,
                  time=time, threading=threading, logger=Mock(), datetime=datetime, json=json, io=io, safe_delete=Mock())
        exec(compile(ast.Module(body=[node], type_ignores=[]), "telegram_bot.py", "exec"), ns)
        message = SimpleNamespace(chat=SimpleNamespace(id=1), from_user=SimpleNamespace(first_name="Owner"))
        ns["process_guestgen"](message, "SG", "name", 3, True)
        self.assertEqual(len(documents[0]["items"]), 3)
        self.assertTrue(all(a["activated"] for a in documents[0]["items"]))
        self.assertIn("Created: 3/3", bot.edit_message_text.call_args.kwargs["text"])
        self.assertIn("Activated: 3/3", bot.edit_message_text.call_args.kwargs["text"])

    def test_command_owner_only_and_both_input_modes(self):
        tree = ast.parse(Path("telegram_bot.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "actguest_command")
        node.decorator_list = []
        bot, worker, thread = Mock(), Mock(), Mock()
        ns = dict(active_bot_for=lambda m: bot, command_belongs_to_other_bot=lambda *a: False,
                  is_owner=lambda uid: uid == 1, parse_accounts=self.module.parse_accounts, json=json,
                  threading=SimpleNamespace(Thread=thread), process_guest_activation=worker)
        exec(compile(ast.Module(body=[node], type_ignores=[]), "telegram_bot.py", "exec"), ns)
        message = SimpleNamespace(from_user=SimpleNamespace(id=2), text="/actguest 123 secret")
        ns["actguest_command"](message)
        thread.assert_not_called()
        message.from_user.id = 1
        ns["actguest_command"](message)
        self.assertEqual(thread.call_args.kwargs["args"][1], [{"uid": "123", "password": "secret"}])
        message.text = "/actguest"
        document = SimpleNamespace(file_size=100, file_id="file")
        message.reply_to_message = SimpleNamespace(document=document)
        ns["actguest_command"](message)
        self.assertIs(thread.call_args.kwargs["args"][2], document)


if __name__ == "__main__":
    unittest.main()
