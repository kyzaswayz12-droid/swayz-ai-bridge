import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent.protected_admission_writer import require_engaged_stop

class EngagedStopPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"stop.db"
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,1)")
    def check(self):
        with patch("agent.protected_admission_writer.STOP_DB",str(self.path)):
            return require_engaged_stop()
    def test_explicit_engaged_stop(self):
        self.assertIsNone(self.check())
    def test_released_stop_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE agent_control SET stopped=0")
        with self.assertRaises(PermissionError):
            self.check()
    def test_missing_stop_rejected(self):
        self.path.unlink()
        with self.assertRaises(PermissionError):
            self.check()
    def test_corrupt_stop_rejected(self):
        self.path.write_text("not sqlite")
        with self.assertRaises(PermissionError):
            self.check()
    def test_missing_row_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM agent_control")
        with self.assertRaises(PermissionError):
            self.check()
