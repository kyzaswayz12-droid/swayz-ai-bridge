import unittest
from unittest.mock import patch
from agent.one_shot_activation import run_one_supervised_handoff

class OneShotActivationTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.args=dict(job_id="job1",commit_sha="a"*40,manifest_sha256="b"*64,
            snapshot="/snap/job1",snapshot_root="/snap",
            expected_hashes={"x":"c"*64},image_digest="sha256:"+"d"*64,
            approved_images=frozenset({"sha256:"+"d"*64}),
            queue_db="/state/queue",job_db="/state/jobs",journal_db="/state/journal",
            stop_db="/state/stop",signing_key_file="/etc/swayz/key",
            request_directory="/var/lib/swayz-executor/requests")

    def invoke(self, prepare=None, dispatch=None, **changes):
        args=dict(self.args)
        args.update(changes)
        def default_prepare(**kw):
            self.calls.append("prepare")
            return "/var/lib/swayz-executor/requests/job1.json"
        def default_dispatch(**kw):
            self.calls.append("dispatch")
            return {"state":"passed","cleanup_verified":True}
        with patch("agent.one_shot_activation.os.geteuid",return_value=0), patch(
            "agent.one_shot_activation.prepare_offline_executor_request",
            side_effect=prepare or default_prepare), patch(
            "agent.one_shot_activation.dispatch_prepared_offline_job",
            side_effect=dispatch or default_dispatch):
            return run_one_supervised_handoff(**args)

    def test_successful_one_shot_sequence(self):
        self.assertEqual(self.invoke()["state"],"passed")
        self.assertEqual(self.calls,["prepare","dispatch"])

    def test_preparation_failure_never_dispatches(self):
        def fail(**kw):
            raise PermissionError("Stop engaged")
        with self.assertRaises(PermissionError):
            self.invoke(prepare=fail)
        self.assertEqual(self.calls,[])

    def test_wrong_request_path_never_dispatches(self):
        with self.assertRaises(PermissionError):
            self.invoke(prepare=lambda **kw:"/tmp/untrusted.json")
        self.assertEqual(self.calls,[])

    def test_dispatch_failure_not_retried(self):
        def fail(**kw):
            self.calls.append("dispatch")
            raise RuntimeError("Uncertain executor state")
        with self.assertRaises(RuntimeError):
            self.invoke(dispatch=fail)
        self.assertEqual(self.calls,["prepare","dispatch"])

    def test_wrong_inbox_rejected_before_preparation(self):
        with self.assertRaises(PermissionError):
            self.invoke(request_directory="/tmp/requests")
        self.assertEqual(self.calls,[])

    def test_nonroot_rejected(self):
        with patch("agent.one_shot_activation.os.geteuid",return_value=1000):
            with self.assertRaises(PermissionError):
                run_one_supervised_handoff(**self.args)
