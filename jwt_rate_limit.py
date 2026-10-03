"""Persistent, cross-worker sliding-window quota for the JWT endpoint."""
import math
import sqlite3
import time


class JwtRateLimit:
    LIMIT = 100
    WINDOW = 60

    def __init__(self, path):
        self.path = path

    def reserve(self):
        """Reserve an attempt; return zero if admitted, otherwise retry seconds."""
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS jwt_attempts (created REAL NOT NULL)")
                now = time.time()
                db.execute("DELETE FROM jwt_attempts WHERE created <= ?", (now - self.WINDOW,))
                count, oldest = db.execute("SELECT COUNT(*), MIN(created) FROM jwt_attempts").fetchone()
                if count >= self.LIMIT:
                    return max(1, math.ceil(oldest + self.WINDOW - now))
                db.execute("INSERT INTO jwt_attempts VALUES (?)", (now,))
                return 0
        finally:
            db.close()
