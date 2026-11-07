import hashlib
import hmac
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agent.development_task_intake import provision_task_queue
from agent.held_task_staging import provision_held_tasks
from agent.worker_control_service import WorkerControlService


class StageControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.held = str(root / "held.db")
        self.queue = str(root / "queue.db")
        provision_held_tasks(self.held)
        provision_task_queue(self.queue)
        self.key = b"x" * 32
        self.svc = WorkerControlService(str(root / "replay.db"), str(root / "stop.db"),
                                        str(root / "journal.db"), self.key,
                                        task_db=self.queue, held_db=self.held)
        self.addCleanup(self.svc.close)

    def request(self, action, nonce):
        data = {"action": action, "job_id": "offline-1", "task": "Offline smoke test",
                "nonce": nonce, "timestamp": 1000}
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        signature = hmac.new(self.key, b"SWAYZ-CONTROL-V1\0" + raw, hashlib.sha256).hexdigest()
        return raw, signature

    def test_stage_while_stopped_is_held_not_executable(self):
        self.assertTrue(self.svc.stop.is_stopped())
        result = self.svc.handle(*self.request("stage", "a" * 32), now=1000)
        self.assertEqual(result, {"action": "stage", "job_id": "offline-1", "state": "held"})
        self.assertTrue(self.svc.stop.is_stopped())
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM development_tasks").fetchone()[0], 0)

    def test_replay_and_duplicate_rejected(self):
        raw, sig = self.request("stage", "b" * 32)
        self.svc.handle(raw, sig, now=1000)
        with self.assertRaises(PermissionError):
            self.svc.handle(raw, sig, now=1000)
        with self.assertRaises(sqlite3.IntegrityError):
            self.svc.handle(*self.request("stage", "c" * 32), now=1000)

    def test_develop_still_blocked_by_stop(self):
        with self.assertRaises(PermissionError):
            self.svc.handle(*self.request("develop", "d" * 32), now=1000)

    def test_stage_requires_explicit_configuration(self):
        root = Path(self.tmp.name)
        svc = WorkerControlService(str(root / "replay2.db"), str(root / "stop2.db"),
                                   str(root / "journal2.db"), self.key, task_db=self.queue)
        try:
            with self.assertRaises(PermissionError):
                svc.handle(*self.request("stage", "e" * 32), now=1000)
        finally:
            svc.close()
