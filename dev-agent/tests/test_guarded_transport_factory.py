import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.guarded_transport_factory import build_guarded_transport


class GuardedTransportFactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "control.db"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            conn.execute("INSERT INTO agent_control VALUES(1,0)")
        workspace = self.root / "job1"
        workspace.mkdir()
        self.plan = plan_worker_lifecycle(
            "job1", "sha256:" + "a" * 64, workspace=str(workspace))

    @patch("agent.fixed_docker_transport.subprocess.run")
    def test_stop_changed_after_factory_blocks_run(self, run):
        transport = build_guarded_transport(
            self.plan, server_control_db=str(self.db))
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE agent_control SET stopped=1 WHERE id=1")
        with self.assertRaises(PermissionError):
            transport(list(self.plan.run_argv), capture_output=True,
                      text=True, timeout=120, check=False)
        run.assert_not_called()

    def test_initially_engaged_stop_blocks_factory(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE agent_control SET stopped=1 WHERE id=1")
        with self.assertRaises(PermissionError):
            build_guarded_transport(self.plan, server_control_db=str(self.db))
