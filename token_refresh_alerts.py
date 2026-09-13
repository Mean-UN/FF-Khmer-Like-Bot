"""Compact token refresh reports and durable owner notification retries."""
import re
import sqlite3
import threading
import time
import json
from functools import wraps
from concurrent.futures import Future, ThreadPoolExecutor, as_completed


_refresh_lock = threading.Lock()
_refresh_jobs = {}


def coalesced_refresh(func):
    """Concurrent full-slot callers share one refresh and its result."""
    @wraps(func)
    def wrapped(set_name, slot=None):
        key = (set_name, slot)
        with _refresh_lock:
            future = _refresh_jobs.get(key)
            leader = future is None
            if leader:
                future = _refresh_jobs[key] = Future()
        if not leader:
            return future.result()
        try:
            result = func(set_name, slot)
            future.set_result(result)
            return result
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with _refresh_lock:
                _refresh_jobs.pop(key, None)
    return wrapped


def refresh_stats(output):
    stats = None
    for line in output.splitlines():
        if line.startswith(("REFRESH_STATS ", "REFRESH_PROGRESS ")):
            try:
                candidate = json.loads(line.split(" ", 1)[1])
                if all(type(candidate.get(k)) is int and candidate[k] >= 0 for k in ("refreshed", "failed")):
                    if "unfinished" in candidate and (type(candidate["unfinished"]) is not int or candidate["unfinished"] < 0):
                        continue
                    stats = candidate
            except (ValueError, TypeError, AttributeError):
                pass
    return stats


def failure_report(set_name, slot, output=""):
    def field(label, default):
        match = re.search(rf"{re.escape(label)}:\s*([^\r\n]+)", output)
        return match.group(1).strip() if match else default
    label = f"{set_name.upper()} SLOT {slot}" if slot else set_name.upper()
    duplicates = field("Duplicate UID", "None")
    # Only account identifiers may appear here; never forward raw subprocess logs.
    duplicates = duplicates if re.fullmatch(r"[0-9, ]+|None", duplicates) else "Unknown"
    skipped = field("Duplicate skipped", "0")
    failed = field("Failed token", "Unknown (refresh interrupted)")
    skipped = skipped if skipped.isascii() and skipped.isdigit() else "0"
    failed = failed if failed.isascii() and failed.isdigit() else "Unknown (refresh interrupted)"
    stats = refresh_stats(output)
    extra = []
    if stats is not None:
        failed = str(stats["failed"])
        if "duplicates" in stats and type(stats["duplicates"]) is int:
            skipped = str(max(0, stats["duplicates"]))
        ids = stats.get("duplicate_uids")
        if isinstance(ids, list) and all(isinstance(uid, str) and uid.isascii() and uid.isdigit() for uid in ids):
            duplicates = ", ".join(ids) if ids else "None"
        if "REFRESH_STATS " not in output:
            extra = [f"🔑 Tokens generated: {stats['refreshed']}", f"⏳ Unfinished: {stats.get('unfinished', 0)}", "⚠️ Refresh interrupted before final save/report"]
    return "\n".join([f"⚠️ {label} TOKEN REFRESH FAILED", "━━━━━━━━━━━━━━━━━━",
                      "🔄 UID/PASS Token Refresh Report", "",
                      f"🔁 Duplicate skipped: {skipped}", f"❌ Failed token: {failed}",
                      f"🆔 Duplicate UID: {duplicates[:1000]}", *extra])


class TokenRefreshAlerts:
    def __init__(self, path):
        self.path = path

    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
        return db

    def enqueue(self, text):
        db = self.db()
        try:
            with db:
                db.execute("INSERT INTO alerts(text) VALUES (?)", (text,))
        finally:
            db.close()

    def send_pending(self, bot, owner_id, logger):
        if not owner_id:
            return
        db = self.db()
        try:
            rows = db.execute("SELECT id,text FROM alerts ORDER BY id LIMIT 30").fetchall()
            for key, text in rows:
                try:
                    bot.send_message(owner_id, text, parse_mode=None)
                except Exception:
                    logger.warning("Token refresh alert delivery failed; queued for retry")
                    break
                with db:
                    db.execute("DELETE FROM alerts WHERE id=?", (key,))
        finally:
            db.close()


def refresh_all(targets, refresh, alerts, logger, report_failures=True):
    started = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(refresh, name, slot): (name, slot) for name, slot in targets}
        for future in as_completed(jobs):
            name, slot = jobs[future]
            crashed = False
            try:
                code, output = future.result()
            except Exception:
                code, output = 1, ""
                crashed = True
            if name == "likeff":
                stats = refresh_stats(output)
                results.append((code, stats))
            if code:
                if report_failures or crashed:
                    alerts.enqueue(failure_report(name, slot, output))
                logger.warning("Token refresh failed for %s slot %s; owner alert queued", name, slot)
            else:
                logger.info("Token refresh completed for %s slot %s", name, slot)
    if results:
        seconds = int(time.monotonic() - started)
        unknown = sum(stats is None for _, stats in results)
        refreshed = sum(stats["refreshed"] for _, stats in results if stats is not None)
        failed = sum(stats["failed"] for _, stats in results if stats is not None)
        unfinished = sum(stats.get("unfinished", 0) for _, stats in results if stats is not None)
        suffix = f" (+ {unknown} slots unknown)" if unknown else ""
        token_label = "Tokens generated" if any(stats is not None and "unfinished" in stats for _, stats in results) else "Tokens refreshed"
        alerts.enqueue("\n".join([
            "✅ LIKEFF TOKEN REFRESH COMPLETE" if all(code == 0 for code, _ in results) else "⚠️ LIKEFF TOKEN REFRESH COMPLETE",
            "━━━━━━━━━━━━━━━━━━", f"📦 Slots checked: {len(results)}",
            f"✅ Successful slots: {sum(code == 0 for code, _ in results)}",
            f"⚠️ Slots with failures: {sum(code != 0 for code, _ in results)}",
            f"🔑 {token_label}: {refreshed}{suffix}", f"❌ Failed tokens: {failed}{suffix}",
            *([f"⏳ Unfinished accounts: {unfinished}"] if unfinished else []),
            f"⏱ Duration: {seconds // 60}m {seconds % 60}s",
        ]))
