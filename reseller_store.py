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
                db.execute("CREATE TABLE IF NOT EXISTS seller_owner_alerts (event_id TEXT PRIMARY KEY, sent_at TEXT NOT NULL DEFAULT '')")
                db.execute("CREATE TABLE IF NOT EXISTS seller_billing_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS seller_daily_bills (bill_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, day TEXT NOT NULL, total_cents INTEGER NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, chat_id INTEGER, message_id INTEGER, UNIQUE(user_id, day, total_cents))")
                db.execute("CREATE TABLE IF NOT EXISTS seller_bill_messages (bill_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, PRIMARY KEY (bill_id,chat_id,message_id))")
                db.execute("CREATE TABLE IF NOT EXISTS seller_payment_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, day TEXT NOT NULL, created_at TEXT NOT NULL, actor_id TEXT NOT NULL, action TEXT NOT NULL, before_cents INTEGER NOT NULL, after_cents INTEGER NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS seller_partial_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, command_id TEXT UNIQUE NOT NULL, bill_id INTEGER NOT NULL, cents INTEGER NOT NULL, before_cents INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0, chat_id INTEGER, message_id INTEGER)")
                bill_columns = {row[1] for row in db.execute("PRAGMA table_info(seller_daily_bills)")}
                for name, definition in (("sent_at", "TEXT NOT NULL DEFAULT ''"), ("reminder_sent_at", "TEXT NOT NULL DEFAULT ''"), ("reminder_chat_id", "INTEGER"), ("reminder_message_id", "INTEGER")):
                    if name not in bill_columns:
                        db.execute(f"ALTER TABLE seller_daily_bills ADD COLUMN {name} {definition}")
                # Older versions did not record when a bill was sent. Begin
                # their reminder clock on upgrade instead of guessing its age.
                db.execute("UPDATE seller_daily_bills SET sent_at=? WHERE message_id IS NOT NULL AND sent_at=''", (self.now().isoformat(),))
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
            if updated and likes > 0:
                db.execute("INSERT OR IGNORE INTO seller_owner_alerts (event_id) VALUES (?)", (event_id,))
        return bool(updated)

    def pending_orders(self):
        with self.db() as db:
            return [(row["event_id"], json.loads(row["order_json"])) for row in db.execute("SELECT event_id,order_json FROM seller_events WHERE kind IN ('autolikeff','autolikeff_extend') AND state='charged' AND exported=0 ORDER BY created_at, rowid")]

    def exported(self, event_ids):
        with self.db() as db:
            db.executemany("UPDATE seller_events SET exported=1 WHERE event_id=?", [(key,) for key in event_ids])
            db.executemany("INSERT OR IGNORE INTO seller_owner_alerts (event_id) SELECT event_id FROM seller_events WHERE event_id=? AND state='charged'", [(key,) for key in event_ids])

    def pending_owner_alerts(self):
        with self.db() as db:
            return [dict(row) for row in db.execute(
                "SELECT e.* FROM seller_owner_alerts a JOIN seller_events e ON e.event_id=a.event_id WHERE a.sent_at='' AND e.state='charged' ORDER BY e.created_at, e.rowid LIMIT 20")]

    def owner_alert_sent(self, event_id):
        with self.db() as db:
            db.execute("UPDATE seller_owner_alerts SET sent_at=? WHERE event_id=?", (self.now().isoformat(), event_id))

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

    def history_page(self, user_id, page=1, size=7):
        with self.db() as db:
            count = db.execute("SELECT COUNT(*) FROM seller_events WHERE user_id=?", (str(user_id),)).fetchone()[0]
            pages = max(1, (count + size - 1) // size)
            page = max(1, min(page, pages))
            events = [dict(row) for row in db.execute(
                "SELECT * FROM seller_events WHERE user_id=? ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
                (str(user_id), size, (page - 1) * size))]
        return events, page, pages

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
            previous_paid = db.execute("SELECT cents FROM seller_payments WHERE user_id=? AND day=?", (str(user_id), day)).fetchone()
            before = previous_paid[0] if previous_paid else 0
            db.execute("INSERT INTO seller_payments VALUES (?, ?, ?, ?) ON CONFLICT(user_id, day) DO UPDATE SET cents=excluded.cents, updated_at=excluded.updated_at", (str(user_id), day, total, self.now().isoformat()))
            if before != total:
                db.execute("INSERT INTO seller_payment_history (user_id,day,created_at,actor_id,action,before_cents,after_cents) VALUES (?,?,?,?,?,?,?)", (str(user_id), day, self.now().isoformat(), "legacy", "paid", before, total))
            if command_id:
                db.execute("INSERT INTO seller_payment_commands VALUES (?, ?, ?, ?)", (command_id, str(user_id), day, total))
        return total

    def manual_bill(self, user_id, day=None):
        day = day or self.day()
        with self.db() as db:
            seller = db.execute("SELECT name FROM sellers WHERE user_id=?", (str(user_id),)).fetchone()
            if not seller:
                raise SellerError("Reseller not found")
            events = [dict(row) for row in db.execute("SELECT kind,package,cents FROM seller_events WHERE user_id=? AND day=? AND state='charged'", (str(user_id), day))]
            total = sum(event["cents"] for event in events)
            payload = json.dumps({"name": seller["name"], "events": events})
            db.execute("INSERT OR IGNORE INTO seller_daily_bills (user_id,day,total_cents,payload,status) VALUES (?,?,?,?,?)", (str(user_id), day, total, payload, "pending"))
            return dict(db.execute("SELECT * FROM seller_daily_bills WHERE user_id=? AND day=? AND total_cents=?", (str(user_id), day, total)).fetchone())

    def manual_bill_sent(self, bill_id, chat_id, message_id):
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO seller_bill_messages VALUES (?,?,?)", (bill_id, chat_id, message_id))

    def manual_bill_messages(self, bill_id):
        with self.db() as db:
            return [(row[0], row[1], False) for row in db.execute("SELECT m.chat_id,m.message_id FROM seller_bill_messages m WHERE m.bill_id=? AND NOT EXISTS (SELECT 1 FROM seller_partial_payments p WHERE p.bill_id=m.bill_id AND p.chat_id=m.chat_id AND p.message_id=m.message_id AND p.used=0)", (bill_id,))]

    def prepare_daily_bills(self):
        today = self.day()
        with self.db() as db:
            # Begin automatic billing from the day this worker is enabled.
            # On restart this value remains, allowing missed days to catch up.
            db.execute("INSERT OR IGNORE INTO seller_billing_settings VALUES ('start_day', ?)", (today,))
            start = db.execute("SELECT value FROM seller_billing_settings WHERE key='start_day'").fetchone()[0]
            days = db.execute("SELECT user_id,day,SUM(cents) AS total FROM seller_events WHERE state='charged' AND day>=? AND day<? GROUP BY user_id,day", (start, today)).fetchall()
            for entry in days:
                uid, day, total = entry["user_id"], entry["day"], entry["total"]
                if db.execute("SELECT 1 FROM seller_events WHERE user_id=? AND day=? AND state='pending' LIMIT 1", (uid, day)).fetchone():
                    continue
                if db.execute("SELECT 1 FROM seller_daily_bills WHERE user_id=? AND day=? AND total_cents=?", (uid, day, total)).fetchone():
                    continue
                seller = db.execute("SELECT name FROM sellers WHERE user_id=?", (uid,)).fetchone()
                events = [dict(row) for row in db.execute("SELECT kind,package,cents FROM seller_events WHERE user_id=? AND day=? AND state='charged'", (uid, day))]
                paid = db.execute("SELECT cents FROM seller_payments WHERE user_id=? AND day=?", (uid, day)).fetchone()
                payload = json.dumps({"name": seller["name"], "events": events})
                status = "paid" if paid and paid[0] >= total else "pending"
                db.execute("INSERT OR IGNORE INTO seller_daily_bills (user_id,day,total_cents,payload,status) VALUES (?,?,?,?,?)", (uid, day, total, payload, status))

    def pending_daily_bills(self):
        with self.db() as db:
            return [dict(row) for row in db.execute(
                "SELECT b.* FROM seller_daily_bills b WHERE b.message_id IS NULL "
                "AND b.day>=COALESCE((SELECT value FROM seller_billing_settings WHERE key='start_day'),?) AND b.day<? "
                "AND b.total_cents>0 AND NOT EXISTS (SELECT 1 FROM seller_events e WHERE e.user_id=b.user_id AND e.day=b.day AND e.state='pending') "
                "AND b.total_cents=(SELECT COALESCE(SUM(e.cents),0) FROM seller_events e WHERE e.user_id=b.user_id AND e.day=b.day AND e.state='charged') "
                "AND b.bill_id=(SELECT MAX(n.bill_id) FROM seller_daily_bills n WHERE n.user_id=b.user_id AND n.day=b.day) "
                "ORDER BY b.day,b.bill_id LIMIT 20", (self.day(), self.day()))]

    def daily_bill_sent(self, bill_id, chat_id, message_id):
        with self.db() as db:
            db.execute("UPDATE seller_daily_bills SET chat_id=?,message_id=?,sent_at=? WHERE bill_id=?", (chat_id, message_id, self.now().isoformat(), bill_id))

    def due_bill_reminders(self):
        cutoff = (self.now() - timedelta(hours=24)).isoformat()
        with self.db() as db:
            return [dict(row) for row in db.execute(
                "SELECT b.* FROM seller_daily_bills b WHERE b.message_id IS NOT NULL AND b.sent_at<=? AND b.reminder_sent_at='' "
                "AND b.bill_id=(SELECT MAX(n.bill_id) FROM seller_daily_bills n WHERE n.user_id=b.user_id AND n.day=b.day) "
                "AND COALESCE((SELECT p.cents FROM seller_payments p WHERE p.user_id=b.user_id AND p.day=b.day),0)<b.total_cents "
                "AND b.total_cents=(SELECT COALESCE(SUM(e.cents),0) FROM seller_events e WHERE e.user_id=b.user_id AND e.day=b.day AND e.state='charged') "
                "ORDER BY b.sent_at,b.bill_id LIMIT 20", (cutoff,))]

    def bill_reminder_sent(self, bill_id, chat_id, message_id):
        with self.db() as db:
            db.execute("UPDATE seller_daily_bills SET reminder_chat_id=?,reminder_message_id=?,reminder_sent_at=? WHERE bill_id=? AND reminder_sent_at=''", (chat_id, message_id, self.now().isoformat(), bill_id))

    def bill_paid_amount(self, bill):
        with self.db() as db:
            row = db.execute("SELECT cents FROM seller_payments WHERE user_id=? AND day=?", (bill["user_id"], bill["day"])).fetchone()
        return row[0] if row else 0

    def prepare_partial_payment(self, bill, cents, command_id):
        if type(cents) is not int or cents <= 0:
            raise SellerError("Payment must be a positive amount")
        with self.db() as db:
            row = db.execute("SELECT cents FROM seller_payments WHERE user_id=? AND day=?", (bill["user_id"], bill["day"])).fetchone()
            before = row[0] if row else 0
            if cents > bill["total_cents"] - before:
                raise SellerError("Payment exceeds the amount due")
            previous = db.execute("SELECT id FROM seller_partial_payments WHERE command_id=?", (command_id,)).fetchone()
            if previous:
                raise SellerError("This payment command was already recorded. Use its confirmation message or send a new command.")
            return db.execute("INSERT INTO seller_partial_payments (command_id,bill_id,cents,before_cents) VALUES (?,?,?,?)", (command_id, bill["bill_id"], cents, before)).lastrowid

    def partial_payment_sent(self, intent_id, chat_id, message_id):
        with self.db() as db:
            db.execute("UPDATE seller_partial_payments SET chat_id=?,message_id=? WHERE id=?", (chat_id, message_id, intent_id))

    def payment_history(self, user_id):
        with self.db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM seller_payment_history WHERE user_id=? ORDER BY id DESC", (str(user_id),))]

    def set_bill_status(self, bill_id, status, chat_id, message_id, actor_id=None):
        partial = status.startswith("partial") and status[7:].isascii() and status[7:].isdigit()
        if status not in ("paid", "pending") and not partial:
            raise SellerError("Invalid payment status")
        with self.db() as db:
            bill = db.execute("SELECT * FROM seller_daily_bills WHERE bill_id=?", (bill_id,)).fetchone()
            manual = db.execute("SELECT 1 FROM seller_bill_messages WHERE bill_id=? AND chat_id=? AND message_id=?", (bill_id, chat_id, message_id)).fetchone()
            if not bill or (not manual and (chat_id, message_id) not in ((bill["chat_id"], bill["message_id"]), (bill["reminder_chat_id"], bill["reminder_message_id"]))):
                raise SellerError("This bill message is no longer valid")
            previous = db.execute("SELECT cents FROM seller_payments WHERE user_id=? AND day=?", (bill["user_id"], bill["day"])).fetchone()
            before = previous[0] if previous else 0
            intent = None
            if partial:
                intent = db.execute("SELECT * FROM seller_partial_payments WHERE id=? AND bill_id=? AND chat_id=? AND message_id=?", (int(status[7:]), bill_id, chat_id, message_id)).fetchone()
                if not intent:
                    raise SellerError("Invalid payment confirmation")
                if intent["used"]:
                    raise SellerError("This payment was already recorded. It has not been added again.")
                if intent["before_cents"] != before:
                    raise SellerError("Paid amount has changed. Open a new payment confirmation.")
            latest = db.execute("SELECT MAX(bill_id) FROM seller_daily_bills WHERE user_id=? AND day=?", (bill["user_id"], bill["day"])).fetchone()[0]
            current_total = db.execute("SELECT COALESCE(SUM(cents),0) FROM seller_events WHERE user_id=? AND day=? AND state='charged'", (bill["user_id"], bill["day"])).fetchone()[0]
            if latest != bill_id or current_total != bill["total_cents"]:
                raise SellerError(f"This bill has changed. Open /seller paid {bill['user_id']} {bill['day']} again.")
            amount = before + intent["cents"] if intent else (bill["total_cents"] if status == "paid" else 0)
            if amount > current_total:
                raise SellerError("Payment exceeds the amount due")
            action = "partial" if intent else status
            status = "paid" if amount >= current_total else "pending"
            if intent:
                db.execute("UPDATE seller_partial_payments SET used=1 WHERE id=?", (intent["id"],))
            if before != amount:
                db.execute("INSERT INTO seller_payment_history (user_id,day,created_at,actor_id,action,before_cents,after_cents) VALUES (?,?,?,?,?,?,?)", (bill["user_id"], bill["day"], self.now().isoformat(), str(actor_id if actor_id is not None else chat_id), action, before, amount))
            db.execute("INSERT INTO seller_payments VALUES (?,?,?,?) ON CONFLICT(user_id,day) DO UPDATE SET cents=excluded.cents,updated_at=excluded.updated_at", (bill["user_id"], bill["day"], amount, self.now().isoformat()))
            db.execute("UPDATE seller_daily_bills SET status=? WHERE bill_id=?", (status, bill_id))
        return {**dict(bill), "status": status}
