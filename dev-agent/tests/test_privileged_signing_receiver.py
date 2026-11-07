import unittest
from unittest.mock import patch
from agent.privileged_signing_receiver import receive_authorised_signing_request

class PrivilegedSigningReceiverTests(unittest.TestCase):
    def setUp(self):
        self.identity={"job_id":"job1","commit_sha":"a"*40,
            "proposal_sha256":"b"*64,"manifest_sha256":"c"*64}
        self.trusted=dict(self.identity,snapshot="/private/job1",
            snapshot_root="/private",expected_hashes={"tests/t.py":"d"*64},
            image_digest="sha256:"+"e"*64,
            approved_images=frozenset({"sha256:"+"e"*64}),
            queue_db="/state/queue",job_db="/state/jobs",
            journal_db="/state/journal",stop_db="/state/stop",
            signing_key_file="/etc/swayz/key",
            request_directory="/private/requests")
        self.calls=[]
    def invoke(self, **updates):
        args=dict(identity=self.identity,
            load_trusted_job=lambda **kw:dict(self.trusted),
            require_running=lambda:None,
            prepare=lambda **kw:(self.calls.append(kw) or "/private/requests/job1.json"))
        args.update(updates)
        with patch("agent.privileged_signing_receiver.os.geteuid",return_value=0):
            return receive_authorised_signing_request(**args)
    def test_trusted_metadata_passed_to_existing_signer(self):
        self.assertEqual(self.invoke(),{"state":"admitted","job_id":"job1"})
        self.assertEqual(self.calls[0]["signing_key_file"],"/etc/swayz/key")
        self.assertNotIn("proposal_sha256",self.calls[0])
    def test_worker_cannot_override_trusted_identity(self):
        bad=dict(self.trusted,commit_sha="f"*40)
        with self.assertRaises(PermissionError):
            self.invoke(load_trusted_job=lambda **kw:bad)
        self.assertEqual(self.calls,[])
    def test_incomplete_trusted_metadata_fails(self):
        with self.assertRaises(PermissionError):
            self.invoke(load_trusted_job=lambda **kw:{"job_id":"job1"})
    def test_stop_blocks_signing(self):
        def stopped():
            raise PermissionError("stop")
        with self.assertRaises(PermissionError):
            self.invoke(require_running=stopped)
        self.assertEqual(self.calls,[])
    def test_nonroot_rejected(self):
        with patch("agent.privileged_signing_receiver.os.geteuid",return_value=995):
            with self.assertRaises(PermissionError):
                receive_authorised_signing_request(
                    identity=self.identity,
                    load_trusted_job=lambda **kw:dict(self.trusted),
                    require_running=lambda:None)
    def test_untrusted_extra_path_rejected(self):
        with self.assertRaises(PermissionError):
            self.invoke(load_trusted_job=lambda **kw:dict(self.trusted,override="/tmp"))
