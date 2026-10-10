"""Local subscriber entitlement registry; no payment processing or messaging."""
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Entitlement:
    subscriber_id: str
    tier: str
    expires_at: int
    active: bool

class SubscriberRegistry:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        with self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS subscriber_entitlements (
                subscriber_id TEXT PRIMARY KEY,
                tier TEXT NOT NULL CHECK(tier IN ('free','premium')),
                expires_at INTEGER NOT NULL,
                active INTEGER NOT NULL CHECK(active IN (0,1))
            )""")

    def grant(self, subscriber_id: str, tier: str, expires_at: int) -> None:
        if not subscriber_id or tier not in ("free","premium") or type(expires_at) is not int or expires_at <= 0:
            raise ValueError("Invalid entitlement")
        with self.conn:
            self.conn.execute(
                "INSERT INTO subscriber_entitlements(subscriber_id,tier,expires_at,active) "
                "VALUES(?,?,?,1) ON CONFLICT(subscriber_id) DO UPDATE SET "
                "tier=excluded.tier,expires_at=excluded.expires_at,active=1",
                (subscriber_id,tier,expires_at))

    def revoke(self, subscriber_id: str) -> bool:
        with self.conn:
            result=self.conn.execute(
                "UPDATE subscriber_entitlements SET active=0 WHERE subscriber_id=? AND active=1",
                (subscriber_id,))
            return result.rowcount==1

    def eligible(self, subscriber_id: str, required_tier: str, now: Optional[int] = None) -> bool:
        if required_tier not in ("free","premium"):
            raise ValueError("Invalid tier")
        timestamp=int(time.time()) if now is None else now
        row=self.conn.execute(
            "SELECT tier,expires_at,active FROM subscriber_entitlements WHERE subscriber_id=?",
            (subscriber_id,)).fetchone()
        if not row:
            return False
        tier,expiry,active=row
        return bool(active) and expiry > timestamp and (required_tier=="free" or tier=="premium")

    def close(self):
        self.conn.close()
