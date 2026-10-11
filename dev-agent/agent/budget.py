"""Atomic daily reservation ledger for estimated model costs.

Reservations count against the cap even if a worker crashes. Only a trusted
server-side settlement operation may release unused amounts.
"""
from dataclasses import dataclass
from decimal import Decimal
import sqlite3
from datetime import datetime, timezone

@dataclass(frozen=True)
class BudgetLimits:
    daily_usd: Decimal = Decimal("5.00")
    daily_calls: int = 20
    per_request_usd: Decimal = Decimal("0.50")

    def __post_init__(self):
        if (not self.daily_usd.is_finite() or self.daily_usd <= 0 or
            not self.per_request_usd.is_finite() or self.per_request_usd <= 0 or
            self.per_request_usd > self.daily_usd or
            type(self.daily_calls) is not int or self.daily_calls < 1):
            raise ValueError("Invalid budget limits")

class BudgetStore:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS reservations (
            request_id TEXT PRIMARY KEY, day_utc TEXT NOT NULL,
            reserved_usd TEXT NOT NULL, status TEXT NOT NULL
            CHECK(status IN ('reserved','settled')),
            actual_usd TEXT)""")

    def reserve(self, request_id: str, estimated_usd: Decimal,
                limits: BudgetLimits, now: datetime) -> bool:
        if not request_id or len(request_id) > 128 or not now.tzinfo or now.utcoffset() is None:
            raise ValueError("Invalid request or clock")
        if not isinstance(estimated_usd, Decimal) or not estimated_usd.is_finite() or not (0 < estimated_usd <= limits.per_request_usd):
            raise ValueError("Invalid cost estimate")
        day = now.astimezone(timezone.utc).date().isoformat()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM reservations WHERE request_id=?", (request_id,)).fetchone():
                self.db.execute("COMMIT")
                return False
            rows = self.db.execute("SELECT reserved_usd,actual_usd FROM reservations WHERE day_utc=?", (day,)).fetchall()
            used = sum((Decimal(actual if actual is not None else reserved) for reserved, actual in rows), Decimal("0"))
            if len(rows) >= limits.daily_calls or used + estimated_usd > limits.daily_usd:
                raise ValueError("Daily model budget exhausted")
            self.db.execute("INSERT INTO reservations VALUES(?,?,?,?,?)",
                            (request_id, day, str(estimated_usd), "reserved", None))
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def settle(self, request_id: str, actual_usd: Decimal) -> None:
        if not isinstance(actual_usd, Decimal) or not actual_usd.is_finite() or actual_usd < 0:
            raise ValueError("Invalid actual cost")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT reserved_usd,status FROM reservations WHERE request_id=?", (request_id,)).fetchone()
            if row is None or row[1] != "reserved":
                raise ValueError("Unknown or already settled request")
            if actual_usd > Decimal(row[0]):
                raise ValueError("Actual cost exceeds reserved amount; halt dispatch")
            self.db.execute("UPDATE reservations SET status=?,actual_usd=? WHERE request_id=?",
                            ("settled", str(actual_usd), request_id))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise


    def summary(self, day_utc: str) -> dict:
        """Read-only view: settled charges and unresolved holds stay distinct."""
        from datetime import date
        if not isinstance(day_utc,str):
            raise ValueError("Invalid UTC date")
        try:
            if date.fromisoformat(day_utc).isoformat()!=day_utc:
                raise ValueError("Invalid UTC date")
        except (TypeError,ValueError):
            raise ValueError("Invalid UTC date") from None
        rows=self.db.execute(
            "SELECT reserved_usd,status,actual_usd FROM reservations WHERE day_utc=?",
            (day_utc,)).fetchall()
        settled=Decimal("0")
        pending=Decimal("0")
        for reserved,status,actual in rows:
            if status=="settled":
                if actual is None:
                    raise ValueError("Corrupt settled ledger entry")
                settled+=Decimal(actual)
            elif status=="reserved":
                pending+=Decimal(reserved)
            else:
                raise ValueError("Corrupt ledger status")
        return {"day_utc":day_utc,"requests":len(rows),
                "settled_usd":str(settled),"pending_reserved_usd":str(pending),
                "accounted_usd":str(settled+pending),
                "actual_provider_billing_verified":False}

    def close(self):
        self.db.close()
