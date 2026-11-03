import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.persistent_stop_guard import PersistentStopGuard


class PersistentStopGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "control.db"
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES (1,1)")

    def test_engaged_stop_rejected(self):
        with self.assertRaises(PermissionError):
            PersistentStopGuard(str(self.path)).require_running()

    def test_running_record_accepted(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE agent_control SET stopped=0 WHERE id=1")
        self.assertIsNone(PersistentStopGuard(str(self.path)).require_running())

    def test_missing_record_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM agent_control")
        with self.assertRaises(PermissionError):
            PersistentStopGuard(str(self.path)).require_running()

    def test_missing_database_rejected_without_creation(self):
        missing = Path(self.temp.name) / "missing.db"
        with self.assertRaises(PermissionError):
            PersistentStopGuard(str(missing))
        self.assertFalse(missing.exists())

    def test_removed_database_rejected(self):
        guard = PersistentStopGuard(str(self.path))
        self.path.unlink()
        with self.assertRaises(PermissionError):
            guard.require_running()

    def test_symlink_rejected(self):
        link = Path(self.temp.name) / "link.db"
        link.symlink_to(self.path)
        with self.assertRaises(PermissionError):
            PersistentStopGuard(str(link))
