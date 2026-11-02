"""Persistent, fail-closed emergency stop for development-agent dispatch.

All model and GitHub actions must check this state immediately before dispatch.
This module never starts a worker or performs external actions.
"""
import sqlite3
from pathlib import Path

class EmergencyStop:
    def __init__(self, path: str):
        if path == ":memory:":
            self.db = sqlite3.connect(path, isolation_level=None, timeout=10, check_same_thread=False)
        else:
            p=Path(path)
            if not p.parent.is_dir() or p.is_symlink():
                raise ValueError("Invalid emergency-stop database path")
            self.db = sqlite3.connect(str(p), isolation_level=None, timeout=10, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS agent_control(
            id INTEGER PRIMARY KEY CHECK(id=1),
            stopped INTEGER NOT NULL CHECK(stopped IN (0,1))
        )""")
        self.db.execute("INSERT OR IGNORE INTO agent_control(id,stopped) VALUES(1,1)")

    def is_stopped(self) -> bool:
        row=self.db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchone()
        return row is None or row[0] != 0

    def require_running(self) -> None:
        if self.is_stopped():
            raise PermissionError("Development agent emergency stop engaged")

    def stop(self) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row=self.db.execute("UPDATE agent_control SET stopped=1 WHERE id=1")
            if row.rowcount != 1:
                raise ValueError("Missing control record")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def enable(self, *, owner_authorised: bool = False) -> None:
        # Caller-provided boolean is NOT identity authentication; do not expose
        # this method via a network endpoint without a verified owner session.
        if owner_authorised is not True:
            raise PermissionError("Owner authorisation required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row=self.db.execute("UPDATE agent_control SET stopped=0 WHERE id=1")
            if row.rowcount != 1:
                raise ValueError("Missing control record")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self) -> None:
        self.db.close()
