import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent.restricted_dispatch import dispatch_prepared_offline_job

class RestrictedDispatchAcceptanceTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root=Path(t.name)
        self.stop=str(root/"stop.db")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        self.snapshot_root=str(root/"snapshots")
        self.snapshot=str(Path(self.snapshot_root)/"job1")
        self.calls=[]

    def executor(self, **kwargs):
        self.calls.append(kwargs)
        kwargs["require_running"]()
        return {"state":"passed","cleanup_verified":True}

    def invoke(self, **changes):
        self.executor.swayz_test_double=True
        args=dict(job_id="job1",snapshot=self.snapshot,
            snapshot_root=self.snapshot_root,expected_hashes={"test.py":"a"*64},
            signing_key_path="/protected/key",stop_db=self.stop,execute=self.executor)
        args.update(changes)
        with patch("agent.restricted_dispatch.os.geteuid",return_value=0):
            return dispatch_prepared_offline_job(**args)

    def test_dispatches_once_with_fixed_identity(self):
        self.assertEqual(self.invoke()["state"],"passed")
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0]["job_id"],"job1")

    def test_stop_prevents_dispatch(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=1")
        with self.assertRaises(PermissionError):
            self.invoke()
        self.assertEqual(self.calls,[])

    def test_wrong_snapshot_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(snapshot="/tmp/other")
        self.assertEqual(self.calls,[])

    def test_failed_cleanup_is_blocked(self):
        def failed(**kwargs):
            return {"state":"passed","cleanup_verified":False}
        failed.swayz_test_double=True
        self.assertEqual(self.invoke(execute=failed)["state"],"blocked")

    def test_untrusted_executor_injection_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(execute=lambda **kwargs:{"state":"passed","cleanup_verified":True})
        self.assertEqual(self.calls,[])

    def test_nonroot_operator_rejected(self):
        with patch("agent.restricted_dispatch.os.geteuid",return_value=1000):
            with self.assertRaises(PermissionError):
                dispatch_prepared_offline_job(job_id="job1",snapshot=self.snapshot,
                    snapshot_root=self.snapshot_root,expected_hashes={},
                    signing_key_path="/protected/key",stop_db=self.stop)
