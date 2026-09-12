"""Owner-added reseller request credits and daily per-purchase billing."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from reseller_pricing import package_price_cents

ICT = timezone(timedelta(hours=7))


class SellerError(ValueError):
    pass


class ResellerStore:
    def __init__(self, path):
        self.path = path

    def now(self):
        return datetime.now(ICT)

    def day(self):
        return (self.now() - timedelta(hours=3)).date().isoformat()

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS sellers (user_id TEXT PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL, granted_requests INTEGER NOT NULL, active INTEGER NOT NULL)")
                columns = {row[1] for row in db.execute("PRAGMA table_info(sellers)")}
                if "daily_limit" in columns:
                    # Convert the old allowance into a one-time grant. All
                    # recorded consumption still counts; no rollover refill.
                    db.execute("ALTER TABLE sellers RENAME COLUMN daily_limit TO granted_requests")
                db.execute("CREATE TABLE IF NOT EXISTS seller_grants (grant_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, requests INTEGER NOT NULL, created_at TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS seller_events (event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, day TEXT NOT NULL, created_at TEXT NOT NULL, kind TEXT NOT NULL, uid TEXT NOT NULL, package INTEGER NOT NULL, cents INTEGER NOT NULL, state TEXT NOT NULL, likes INTEGER NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '', order_json TEXT, exported INTEGER NOT NULL DEFAULT 0)")
                db.execute("CREATE TABLE IF NOT EXISTS seller_payments (user_id TEXT NOT NULL, day TEXT NOT NULL, cents INTEGER NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(user_id, day))")
                db.execute("CREATE TABLE IF NOT EXISTS seller_payment_commands (command_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, day TEXT NOT NULL, cents INTEGER NOT NULL)")
                db.execute("CREATE INDEX IF NOT EXISTS seller_event_day ON seller_events(user_id, day)")
                # Recover holds left by crashed workers. Normal API calls time
                # out after 120 seconds and release their hold immediately.
                db.execute("UPDATE seller_events SET state='void', detail='No confirmed result; expired request hold released' WHERE kind='likeff' AND state='pending' AND created_at < ?", ((self.now() - timedelta(minutes=10)).isoformat(),))
                yield db
        finally:
            db.close()

    def seller(self, user_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM sellers WHERE user_id=?", (str(user_id),)).fetchone()
        return dict(row) if row else None

    def configure(self, user_id, name, username, requests, grant_id=None):
        if type(requests) is not int or not 0 < requests <= 9223372036854775807:
            raise SellerError("Requests to add must be a positive number")
        grant_id = grant_id or uuid.uuid4().hex
        with self.db() as db:
            if db.execute("SELECT 1 FROM seller_grants WHERE grant_id=?", (grant_id,)).fetchone():
                raise SellerError("This request top-up was already recorded")
            previous = db.execute("SELECT granted_requests FROM sellers WHERE user_id=?", (str(user_id),)).fetchone()
            if previous and previous[0] > 9223372036854775807 - requests:
                raise SellerError("Request total is too large")
            db.execute("INSERT INTO seller_grants VALUES (?, ?, ?, ?)", (grant_id, str(user_id), requests, self.now().isoformat()))
            db.execute("INSERT INTO sellers VALUES (?, ?, ?, ?, 1) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username, granted_requests=sellers.granted_requests+excluded.granted_requests, active=1", (str(user_id), name, username, requests))

    def remember(self, user_id, name, username):
        with self.db() as db:
            db.execute("UPDATE sellers SET name=?, username=? WHERE user_id=?", (name, username, str(user_id)))

    def disable(self, user_id):
        with self.db() as db:
            if not db.execute("UPDATE sellers SET active=0 WHERE user_id=?", (str(user_id),)).rowcount:
                raise SellerError("Reseller not found")

    def reserve(self, user_id, event_id, kind, uid, package=0, order=None):
        if kind not in ("likeff", "autolikeff", "autolikeff_extend"):
            raise SellerError("Unsupported reseller operation")
        cents = 20 if kind == "likeff" else package_price_cents(package)
        day = self.day()
        with self.db() as db:
            if db.execute("SELECT 1 FROM seller_events WHERE event_id=?", (event_id,)).fetchone():
                raise SellerError("This command was already recorded. Use /seller history to check it.")
            seller = db.execute("SELECT * FROM sellers WHERE user_id=?", (str(user_id),)).fetchone()
            if not seller or not seller["active"]:
                raise SellerError("Reseller access is disabled")
            used = db.execute("SELECT COUNT(*) FROM seller_events WHERE user_id=? AND state IN ('pending', 'charged')", (str(user_id),)).fetchone()[0]
            if used >= seller["granted_requests"]:
                raise SellerError("No reseller requests available. Ask the owner to add requests. There is no automatic reset.")
            state = "pending" if kind == "likeff" else "charged"
            db.execute("INSERT INTO seller_events (event_id,user_id,name,day,created_at,kind,uid,package,cents,state,order_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (event_id, str(user_id), seller["name"], day, self.now().isoformat(), kind, str(uid), package, cents, state, json.dumps(order) if order else None))
        return event_id

    def finish_manual(self, event_id, likes, detail=""):
        with self.db() as db:
            updated = db.execute("UPDATE seller_events SET state=?, likes=?, detail=? WHERE event_id=? AND state='pending' AND kind='likeff'", ("charged" if likes > 0 else "void", max(0, likes), detail, event_id)).rowcount
        return bool(updated)

    def pending_orders(self):
        with self.db() as db:
            return [(row["event_id"], json.loads(row["order_json"])) for row in db.execute("SELECT event_id,order_json FROM seller_events WHERE kind IN ('autolikeff','autolikeff_extend') AND state='charged' AND exported=0 ORDER BY created_at, rowid")]

    def exported(self, event_ids):
        with self.db() as db:
            db.executemany("UPDATE seller_events SET exported=1 WHERE event_id=?", [(key,) for key in event_ids])

    def record_order(self, order):
        key = order.get("seller_event_id")
        if key:
            with self.db() as db:
                sent = int(order.get("sent_likes", 0))
                detail = order.get("last_error") or order.get("status", "active")
                db.execute("UPDATE seller_events SET likes=MAX(likes, MIN(package, ?)), detail=? WHERE event_id=?", (sent, detail, key))
                for extension in order.get("seller_extensions", []):
                    delivered = max(0, sent - extension["offset"])
                    db.execute("UPDATE seller_events SET likes=MAX(likes, MIN(package, ?)), detail=? WHERE event_id=?", (delivered, detail, extension["event_id"]))

    def history(self, user_id=None, day=None, page=1, size=20):
        clauses, params = [], []
        if user_id is not None:
            clauses.append("user_id=?")
            params.append(str(user_id))
        if day is not None:
            clauses.append("day=?")
            params.append(day)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM seller_events" + where + " ORDER BY created_at DESC, event_id DESC LIMIT ? OFFSET ?", (*params, size, (page - 1) * size))]

    def report(self, user_id=None, day=None):
        day = day or self.day()
        with self.db() as db:
            sellers = db.execute("SELECT * FROM sellers" + (" WHERE user_id=?" if user_id is not None else "") + " ORDER BY name", (str(user_id),) if user_id is not None else ()).fetchall()
            reports = []
            for seller in sellers:
                events = [dict(row) for row in db.execute("SELECT * FROM seller_events WHERE user_id=? AND day=?", (seller["user_id"], day))]
                charged = [e for e in events if e["state"] == "charged"]
                paid = db.execute("SELECT cents FROM seller_payments WHERE user_id=? AND day=?", (seller["user_id"], day)).fetchone()
                consumed = db.execute("SELECT COUNT(*) FROM seller_events WHERE user_id=? AND state='charged'", (seller["user_id"],)).fetchone()[0]
                pending = db.execute("SELECT COUNT(*) FROM seller_events WHERE user_id=? AND state='pending'", (seller["user_id"],)).fetchone()[0]
                reports.append({**dict(seller), "day": day, "events": events, "used": len(charged), "pending": pending,
                                "consumed": consumed, "remaining": max(0, seller["granted_requests"] - consumed - pending),
                                "cents": sum(e["cents"] for e in charged), "paid": paid[0] if paid else 0})
        return reports

    def mark_paid(self, user_id, day, command_id=None):
        # Record the current bill amount, so later purchases remain unpaid.
        with self.db() as db:
            if command_id:
                previous = db.execute("SELECT cents FROM seller_payment_commands WHERE command_id=?", (command_id,)).fetchone()
                if previous:
                    return previous[0]
            if not db.execute("SELECT 1 FROM sellers WHERE user_id=?", (str(user_id),)).fetchone():
                raise SellerError("Reseller not found")
            total = db.execute("SELECT COALESCE(SUM(cents),0) FROM seller_events WHERE user_id=? AND day=? AND state='charged'", (str(user_id), day)).fetchone()[0]
            db.execute("INSERT INTO seller_payments VALUES (?, ?, ?, ?) ON CONFLICT(user_id, day) DO UPDATE SET cents=excluded.cents, updated_at=excluded.updated_at", (str(user_id), day, total, self.now().isoformat()))
            if command_id:
                db.execute("INSERT INTO seller_payment_commands VALUES (?, ?, ?, ?)", (command_id, str(user_id), day, total))
        return total
