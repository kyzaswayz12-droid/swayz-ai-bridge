"""Authenticated develop control integration, without provider or Docker calls."""
import hashlib
import hmac
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from agent.worker_control_service import WorkerControlService
from agent.development_task_intake import provision_task_queue


class DevelopControlIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.stop = str(root / "stop.db")
        self.queue = str(root / "queue.db")
        self.jobs = str(root / "jobs.db")
        provision_task_queue(self.queue)
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        self.key = b"k" * 32
        self.service = WorkerControlService(
            str(root / "replay.db"), self.stop, str(root / "journal.db"),
            self.key, task_db=self.queue, job_db=self.jobs)
        self.addCleanup(self.service.close)

    def signed(self, *, nonce="a"*32, action="develop", task="Fix tests"):
        data = dict(action=action, job_id="slack-123", nonce=nonce, timestamp=1000)
        if action == "develop":
            data["task"] = task
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        sig = hmac.new(self.key, b"SWAYZ-CONTROL-V1\0" + raw, hashlib.sha256).hexdigest()
        return raw, sig

    def test_signed_develop_queues_once(self):
        raw, sig = self.signed()
        result = self.service.handle(raw, sig, now=1000)
        self.assertEqual(result, dict(action="develop", job_id="slack-123", state="queued"))
        with sqlite3.connect(self.queue) as db:
            self.assertEqual(db.execute("SELECT task,state FROM development_tasks").fetchone(),
                             ("Fix tests", "queued"))
        with self.assertRaises(PermissionError):
            self.service.handle(raw, sig, now=1000)

    def test_job_status_reports_durable_queue(self):
        raw, sig = self.signed()
        self.service.handle(raw, sig, now=1000)
        raw2, sig2 = self.signed(nonce="c"*32, action="job_status")
        result = self.service.handle(raw2, sig2, now=1000)
        self.assertEqual(result["state"], "queued")

    def test_stopped_control_blocks_submission(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1 WHERE id=1")
        raw, sig = self.signed()
        with self.assertRaises(PermissionError):
            self.service.handle(raw, sig, now=1000)

    def test_missing_task_rejected(self):
        raw, sig = self.signed(task="")
        with self.assertRaises(ValueError):
            self.service.handle(raw, sig, now=1000)

    def test_unconfigured_service_refuses_develop(self):
        with tempfile.TemporaryDirectory() as d:
            service = WorkerControlService(
                str(Path(d)/"replay.db"), self.stop, str(Path(d)/"journal.db"), self.key)
            self.addCleanup(service.close)
            raw, sig = self.signed(nonce="b"*32)
            with self.assertRaises(PermissionError):
                service.handle(raw, sig, now=1000)
