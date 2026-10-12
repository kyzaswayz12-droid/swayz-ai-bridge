"""Conservative combined GBP API reservation ledger (offline, no API dispatch).

Uses a shared persistent SQLite database for both providers. The caller must
supply an independently approved conservative USD-to-GBP conversion rate.
This module does not verify provider billing or authorise unattended dispatch.
"""
from datetime import datetime, timezone
from decimal import Decimal
import sqlite3


class GBPBudget:
    def __init__(self, path):
        if not path or path == ":memory:":
            raise ValueError("Persistent database path required")
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS gbp_reservations (
            request_id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            day_utc TEXT NOT NULL,
            reserved_gbp TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('reserved','settled')),
            actual_gbp TEXT
        )""")

    def reserve(self, request_id, provider, maximum_usd, gbp_per_usd,
                now, *, daily_cap_gbp=Decimal("5.00")):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise ValueError("Invalid request ID")
        if provider not in ("openai", "anthropic"):
            raise ValueError("Unapproved provider")
        for amount in (maximum_usd, gbp_per_usd, daily_cap_gbp):
            if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
                raise ValueError("Invalid conversion or budget")
        if daily_cap_gbp != Decimal("5.00"):
            raise ValueError("Daily cap must be GBP 5")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware clock required")
        reserved = maximum_usd * gbp_per_usd
        day = now.astimezone(timezone.utc).date().isoformat()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute(
                "SELECT 1 FROM gbp_reservations WHERE request_id=?", (request_id,)
            ).fetchone():
                self.db.execute("COMMIT")
                return False
            rows = self.db.execute(
                "SELECT reserved_gbp,actual_gbp FROM gbp_reservations WHERE day_utc=?",
                (day,)
            ).fetchall()
            used = sum((Decimal(actual if actual is not None else held)
                        for held, actual in rows), Decimal("0"))
            if used + reserved > daily_cap_gbp:
                raise ValueError("Daily GBP API budget exhausted")
            self.db.execute(
                "INSERT INTO gbp_reservations VALUES (?,?,?,?,?,?)",
                (request_id, provider, day, str(reserved), "reserved", None)
            )
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def settle(self, request_id, actual_gbp):
        if not isinstance(actual_gbp, Decimal) or not actual_gbp.is_finite() or actual_gbp < 0:
            raise ValueError("Invalid actual cost")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT reserved_gbp,status FROM gbp_reservations WHERE request_id=?",
                (request_id,)
            ).fetchone()
            if row is None or row[1] != "reserved":
                raise ValueError("Unknown or already settled request")
            if actual_gbp > Decimal(row[0]):
                raise ValueError("Actual cost exceeds reservation; halt dispatch")
            self.db.execute(
                "UPDATE gbp_reservations SET status='settled',actual_gbp=? WHERE request_id=?",
                (str(actual_gbp), request_id)
            )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()
