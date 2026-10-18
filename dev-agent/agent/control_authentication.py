"""Fail-closed, replay-resistant authenticated control messages.

Transport TLS and key distribution are external requirements. This module
does not start a network listener, Docker, or an autonomous agent.
"""
import hashlib
import hmac
import json
import re
import sqlite3
import time

_ACTIONS = {"status", "stop", "job_status"}
_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_NONCE = re.compile(r"^[a-f0-9]{32,64}$")


class ControlAuthenticator:
    def __init__(self, database_path, key):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("Control key must contain at least 32 bytes")
        if database_path == ":memory:" or not isinstance(database_path, str) or not database_path:
            raise ValueError("Persistent replay database required")
        self._key = key
        self.db = sqlite3.connect(database_path, timeout=10, isolation_level=None, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("CREATE TABLE IF NOT EXISTS control_nonces (nonce TEXT PRIMARY KEY, seen_at INTEGER NOT NULL)")

    def verify(self, raw, signature, *, now=None):
        if not isinstance(raw, bytes) or len(raw) > 1024 or not isinstance(signature, str):
            raise ValueError("Invalid request")
        if not re.fullmatch(r"[a-f0-9]{64}", signature):
            raise ValueError("Invalid signature format")
        expected = hmac.new(self._key, b"SWAYZ-CONTROL-V1\0" + raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PermissionError("Invalid request signature")
        try:
            data = json.loads(raw)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("Invalid request JSON") from exc
        if not isinstance(data, dict) or set(data) != {"action", "job_id", "nonce", "timestamp"}:
            raise ValueError("Invalid control schema")
        if data["action"] not in _ACTIONS:
            raise PermissionError("Unsupported control action")
        if data["action"] == "job_status":
            if not isinstance(data["job_id"], str) or not _JOB.fullmatch(data["job_id"]):
                raise ValueError("Invalid job ID")
        elif data["job_id"] is not None:
            raise ValueError("Unexpected job ID")
        if not isinstance(data["nonce"], str) or not _NONCE.fullmatch(data["nonce"]):
            raise ValueError("Invalid nonce")
        current = int(time.time()) if now is None else int(now)
        if type(data["timestamp"]) is not int or abs(current - data["timestamp"]) > 60:
            raise PermissionError("Stale control request")
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        if canonical != raw:
            raise ValueError("Noncanonical request")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("DELETE FROM control_nonces WHERE seen_at < ?", (current - 3600,))
            inserted = self.db.execute("INSERT OR IGNORE INTO control_nonces(nonce,seen_at) VALUES(?,?)",
                                       (data["nonce"], current))
            if inserted.rowcount != 1:
                raise PermissionError("Replayed control request")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return data

    def close(self):
        self.db.close()
