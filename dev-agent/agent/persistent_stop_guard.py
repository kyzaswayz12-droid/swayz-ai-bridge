"""Read-only emergency-stop check for local worker execution.

The privileged service must configure the authoritative control database
path independently of job payloads. This module cannot enable the stop.
"""
import sqlite3
from pathlib import Path


class PersistentStopGuard:
    def __init__(self, control_db: str):
        p = Path(control_db)
        if not p.is_absolute() or p.is_symlink() or not p.is_file():
            raise PermissionError("Authoritative control database unavailable")
        self.path = p

    def require_running(self):
        p = self.path
        if p.is_symlink() or not p.is_file():
            raise PermissionError("Control database changed or missing")
        try:
            with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
                rows = db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchall()
        except sqlite3.Error as exc:
            raise PermissionError("Control database unavailable") from exc
        if rows != [(0,)]:
            raise PermissionError("Emergency stop engaged or invalid")
        return None
