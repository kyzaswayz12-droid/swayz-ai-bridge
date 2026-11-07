import unittest
from unittest.mock import patch
from agent.protected_admission_writer import write_protected_admission

class ProtectedAdmissionWriterTests(unittest.TestCase):
    def setUp(self):
        self.args=dict(job_id="job1",commit_sha="a"*40,
            proposal_sha256="b"*64,manifest_sha256="c"*64,
            expected_hashes={"tests/test.py":"d"*64},
            image_digest="sha256:"+"e"*64,
            approved_images=frozenset({"sha256:"+"e"*64}),
            signing_key_file="/etc/swayz/executor-signing.key",
            require_operator=lambda **kw:True)
    def invoke(self,**updates):
        args=dict(self.args,**updates)
        with patch("agent.protected_admission_writer.os.geteuid",return_value=0):
            return write_protected_admission(**args)
    def test_missing_operator_denied(self):
        with self.assertRaises(PermissionError):
            self.invoke(require_operator=lambda **kw:False)
    def test_invalid_job_denied(self):
        with self.assertRaises(PermissionError):
            self.invoke(job_id="../unsafe")
    def test_wrong_key_path_denied(self):
        with self.assertRaises(PermissionError):
            self.invoke(signing_key_file="/tmp/key")
    def test_unapproved_image_denied(self):
        with self.assertRaises(PermissionError):
            self.invoke(approved_images=frozenset())
    def test_unsafe_hash_path_denied(self):
        with self.assertRaises(PermissionError):
            self.invoke(expected_hashes={"../key":"d"*64})
    def test_nonroot_denied(self):
        with patch("agent.protected_admission_writer.os.geteuid",return_value=995):
            with self.assertRaises(PermissionError):
                write_protected_admission(**self.args)
