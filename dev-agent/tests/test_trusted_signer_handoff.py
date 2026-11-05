import unittest
from types import SimpleNamespace
from agent.trusted_signer_handoff import submit_to_trusted_signer

class TrustedSignerHandoffTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.plan=SimpleNamespace(base_sha="a"*40,proposal_sha256="b"*64)
        self.snapshot={"job_id":"job1","commit_sha":"a"*40,
            "proposal_sha256":"b"*64,"snapshot":"/private/job1",
            "snapshot_root":"/private","expected_hashes":{"tests/test.py":"c"*64},
            "manifest_sha256":"d"*64,"image_digest":"sha256:"+"e"*64}
    def signer(self, **kwargs):
        self.calls.append(kwargs)
        return {"state":"admitted","job_id":kwargs["job_id"]}
    def invoke(self, **changes):
        args=dict(job_id="job1",plan=self.plan,
            prepared_snapshot=self.snapshot,require_running=lambda:None,
            signer_request=self.signer)
        args.update(changes)
        return submit_to_trusted_signer(**args)
    def test_admitted_identity_bound(self):
        self.assertEqual(self.invoke(),{"state":"admitted","job_id":"job1"})
        self.assertEqual(self.calls[0]["proposal_sha256"],"b"*64)
        self.assertNotIn("snapshot",self.calls[0])
    def test_wrong_proposal_rejected_before_signing(self):
        with self.assertRaises(PermissionError):
            self.invoke(plan=SimpleNamespace(base_sha="a"*40,proposal_sha256="f"*64))
        self.assertEqual(self.calls,[])
    def test_path_traversal_rejected(self):
        snapshot=dict(self.snapshot,expected_hashes={"../secret":"c"*64})
        with self.assertRaises(PermissionError):
            self.invoke(prepared_snapshot=snapshot)
        self.assertEqual(self.calls,[])
    def test_stop_rejected_before_signing(self):
        with self.assertRaises(PermissionError):
            self.invoke(require_running=lambda: (_ for _ in ()).throw(PermissionError("stop")))
        self.assertEqual(self.calls,[])
    def test_unconfirmed_signer_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(signer_request=lambda **kw:{"state":"queued","job_id":"job1"})
    def test_missing_signer_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(signer_request=None)
