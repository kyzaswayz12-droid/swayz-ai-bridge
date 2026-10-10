"""Durable, approval-gated subscriber outbox. No network sending.

Delivery is at-least-once when external providers are later attached.
"""
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class OutboxItem:
    publication_id: str
    channel: str
    text: str
    status: str
    approved_by: Optional[str]
    attempt_count: int

class PublicationOutbox:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        with self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS publication_outbox (
                publication_id TEXT PRIMARY KEY,
                channel TEXT NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('draft','approved','sending','sent','failed')),
                approved_by TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )""")

    def create_draft(self, publication_id: str, channel: str, text: str) -> None:
        if not publication_id or channel not in ("telegram", "discord"):
            raise ValueError("Invalid publication target")
        if not text.startswith("PAPER TRADE — SIMULATED, NOT REAL MONEY"):
            raise ValueError("Only labelled paper trades may be queued")
        with self.conn:
            self.conn.execute(
                "INSERT INTO publication_outbox(publication_id,channel,text,status,updated_at) VALUES(?,?,?,?,?)",
                (publication_id,channel,text,"draft",time.time()))

    def approve(self, publication_id: str, approver: str, allowed_approvers: set[str]) -> bool:
        if not approver or approver not in allowed_approvers:
            raise PermissionError("Not authorised")
        with self.conn:
            result=self.conn.execute(
                "UPDATE publication_outbox SET status='approved', approved_by=?, updated_at=? "
                "WHERE publication_id=? AND status='draft'",
                (approver,time.time(),publication_id))
            return result.rowcount == 1

    def claim(self, publication_id: str) -> bool:
        """Mark delivery as in-flight. Never automatically retry uncertain sends."""
        with self.conn:
            result=self.conn.execute(
                "UPDATE publication_outbox SET status='sending', attempt_count=attempt_count+1, updated_at=? "
                "WHERE publication_id=? AND status='approved'",
                (time.time(),publication_id))
            return result.rowcount == 1

    def mark_sent(self, publication_id: str) -> bool:
        with self.conn:
            result=self.conn.execute(
                "UPDATE publication_outbox SET status='sent', updated_at=? "
                "WHERE publication_id=? AND status='sending'",
                (time.time(),publication_id))
            return result.rowcount == 1

    def mark_failed(self, publication_id: str) -> bool:
        with self.conn:
            result=self.conn.execute(
                "UPDATE publication_outbox SET status='failed', updated_at=? "
                "WHERE publication_id=? AND status='sending'",
                (time.time(),publication_id))
            return result.rowcount == 1

    def get(self, publication_id: str) -> Optional[OutboxItem]:
        row=self.conn.execute(
            "SELECT publication_id,channel,text,status,approved_by,attempt_count "
            "FROM publication_outbox WHERE publication_id=?", (publication_id,)).fetchone()
        return OutboxItem(*row) if row else None

    def close(self):
        self.conn.close()
