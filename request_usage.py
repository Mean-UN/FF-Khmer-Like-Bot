"""Persistent daily LikeFF slot quotas."""
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from flask import jsonify, request

SLOT_LIMIT = 30
SLOT_COUNT = 30
ICT = timezone(timedelta(hours=7))


class SlotUsage:
    def __init__(self, path):
        self.path = path

    def today(self):
        # Before 03:00 ICT, requests belong to the previous quota day.
        return (datetime.now(ICT) - timedelta(hours=3)).date().isoformat()

    @contextmanager
    def database(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS slot_usage (day TEXT, slot INTEGER, used INTEGER NOT NULL, max_limit INTEGER NOT NULL, remaining INTEGER NOT NULL, PRIMARY KEY(day, slot))")
                db.execute("CREATE TABLE IF NOT EXISTS slot_pending (id TEXT PRIMARY KEY, day TEXT, slot INTEGER, expires REAL)")
                db.execute("DELETE FROM slot_pending WHERE expires < ?", (time.time(),))
                yield db
        finally:
            db.close()

    def initialize(self, db, day):
        db.executemany("INSERT OR IGNORE INTO slot_usage VALUES (?, ?, 0, ?, ?)",
                       [(day, slot, SLOT_LIMIT, SLOT_LIMIT) for slot in range(1, SLOT_COUNT + 1)])

    def snapshot(self, slot=None):
        day = self.today()
        with self.database() as db:
            self.initialize(db, day)
            rows = db.execute("SELECT slot, used, max_limit, remaining FROM slot_usage WHERE day=? ORDER BY slot", (day,)).fetchall()
        slots = [dict(zip(("slot", "used", "max_limit", "remaining"), row)) for row in rows]
        if slot is not None:
            return {"date": day, **slots[slot - 1]}
        return {"date": day, "timezone": "Asia/Phnom_Penh", "slots": slots}

    def reserve(self, eligible_slots=None):
        day = self.today()
        eligible_slots = list(range(1, SLOT_COUNT + 1)) if eligible_slots is None else list(eligible_slots)
        if not eligible_slots:
            raise RuntimeError("No LikeFF slots have configured tokens")
        with self.database() as db:
            self.initialize(db, day)
            placeholders = ",".join("?" for _ in eligible_slots)
            row = db.execute(f"SELECT s.slot FROM slot_usage s WHERE s.day=? AND s.slot IN ({placeholders}) AND s.used + (SELECT COUNT(*) FROM slot_pending p WHERE p.day=s.day AND p.slot=s.slot) < s.max_limit ORDER BY s.slot LIMIT 1", (day, *eligible_slots)).fetchone()
            if row is None:
                raise RuntimeError("All LikeFF slots are full or currently busy today")
            key = uuid.uuid4().hex
            # Abandoned reservations expire after a worker crash. Renewals are
            # unnecessary for normal calls, whose HTTP requests have timeouts.
            db.execute("INSERT INTO slot_pending VALUES (?, ?, ?, ?)", (key, day, row[0], time.time() + 3600))
        return key, day, row[0]

    def finish(self, reservation, likes_sent):
        key, day, slot = reservation
        with self.database() as db:
            removed = db.execute("DELETE FROM slot_pending WHERE id=?", (key,)).rowcount
            if removed and likes_sent > 0:
                db.execute("UPDATE slot_usage SET used=used+1, remaining=MAX(0, max_limit-used-1) WHERE day=? AND slot=?", (day, slot))
            row = db.execute("SELECT used, max_limit, remaining FROM slot_usage WHERE day=? AND slot=?", (day, slot)).fetchone()
        return {"date": day, "slot": slot, **dict(zip(("used", "max_limit", "remaining"), row))}


def install_request_usage(app):
    path = os.environ.get("REQUEST_USAGE_DB", os.path.join(app.root_path, "request_usage.sqlite3"))
    tracker = SlotUsage(path)
    app.extensions["slot_usage"] = tracker

    @app.get("/usage", endpoint="request_usage")
    def get_request_usage():
        value = request.args.get("slot")
        if value is not None and (not value.isascii() or not value.isdigit() or not 1 <= int(value) <= SLOT_COUNT):
            return jsonify({"error": "slot must be between 1 and 30"}), 400
        response = jsonify(app.extensions["slot_usage"].snapshot(int(value) if value is not None else None))
        response.headers["Cache-Control"] = "no-store"
        return response
