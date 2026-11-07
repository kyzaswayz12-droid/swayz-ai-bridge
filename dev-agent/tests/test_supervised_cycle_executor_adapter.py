import unittest
from types import SimpleNamespace
from agent.supervised_cycle_executor_adapter import supervised_cycle_executor

class SupervisedCycleExecutorAdapterTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.prepared = {"job_id":"job1","snapshot":"/snap/job1",
            "snapshot_root":"/snap","expected_hashes":{"test.py":"abc"},
            "signing_key_path":"/protected/key","approved_base_sha":"a"*40,"approved_proposal_sha256":"b"*64}
        self.plan = SimpleNamespace(base_sha="a"*40,proposal_sha256="b"*64)

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return {"state":"passed","cleanup_verified":True}

    def invoke(self, **changes):
        args = dict(job_id="job1",plan=self.plan,prepared=self.prepared,
                    require_running=lambda:None,execute=self.execute)
        args.update(changes)
        return supervised_cycle_executor(**args)

    def test_prepared_job_invokes_existing_executor(self):
        self.assertEqual(self.invoke()["state"],"passed")
        self.assertEqual(len(self.calls),1)

    def test_mismatched_job_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(job_id="other")
        self.assertEqual(self.calls,[])

    def test_mismatched_base_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(plan=SimpleNamespace(base_sha="b"*40,proposal_sha256="b"*64))
        self.assertEqual(self.calls,[])

    def test_missing_preparation_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(prepared={})
        self.assertEqual(self.calls,[])

    def test_failed_cleanup_blocks(self):
        result=self.invoke(execute=lambda **kw:{"state":"passed","cleanup_verified":False})
        self.assertEqual(result["state"],"blocked")

    def test_stop_prevents_executor_call(self):
        def stopped():
            raise PermissionError("Stopped")
        with self.assertRaises(PermissionError):
            self.invoke(require_running=stopped)
        self.assertEqual(self.calls,[])

    def test_mismatched_proposal_digest_rejected(self):
        from types import SimpleNamespace
        with self.assertRaises(PermissionError):
            self.invoke(plan=SimpleNamespace(base_sha="a"*40,proposal_sha256="c"*64))
        self.assertEqual(self.calls,[])
