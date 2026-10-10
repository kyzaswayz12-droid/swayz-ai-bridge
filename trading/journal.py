"""Append-only paper trade journal with SQLite transaction boundaries.

Does not place orders or connect to any broker.
"""
import json
import sqlite3
import threading
import time
from dataclasses import asdict
from decimal import Decimal
from typing import Any

class PaperJournal:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        with self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS paper_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL
            )""")

    def append(self, event_id: str, kind: str, payload: dict[str, Any]) -> int:
        if not event_id or kind not in ("order_rejected", "fill", "deposit", "withdrawal", "mark"):
            raise ValueError("Invalid event")
        encoded = json.dumps(payload, sort_keys=True, default=self._serialize, allow_nan=False)
        with self.lock, self.conn:
            cursor = self.conn.execute(
                "INSERT INTO paper_events (event_id,kind,payload,created_at) VALUES (?,?,?,?)",
                (event_id, kind, encoded, time.time()))
            return int(cursor.lastrowid)

    @staticmethod
    def _serialize(value: Any) -> str:
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError("Unsupported journal value")

    def events(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT sequence,event_id,kind,payload FROM paper_events ORDER BY sequence").fetchall()
        return [{"sequence": seq, "event_id": eid, "kind": kind, "payload": json.loads(body)}
                for seq, eid, kind, body in rows]

    def close(self):
        self.conn.close()
