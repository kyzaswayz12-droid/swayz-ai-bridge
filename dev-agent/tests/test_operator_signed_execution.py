import unittest
from unittest.mock import patch
from agent.operator_signed_execution import execute_operator_signed_job

class OperatorSignedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        self.job={"job_id":"job1","stop_db":"/var/lib/swayzcontrol/state/stop.db",
                  "signing_key_file":"/etc/swayz/executor-signing.key",
                  "request_directory":"/var/lib/swayz-executor/requests",
                  "commit_sha":"a"*40,"proposal_sha256":"b"*64,
                  "manifest_sha256":"c"*64,"snapshot":"/snap/job1",
                  "snapshot_root":"/snap","expected_hashes":{"test.py":"d"*64}}
    def invoke(self,**updates):
        def receive(**kw):
            self.events.append("sign")
            return {"state":"admitted","job_id":"job1"}
        def execute(**kw):
            self.events.append("execute")
            return {"state":"passed","cleanup_verified":True}
        opts=dict(job_id="job1",load_job=lambda job_id:dict(self.job),
                  receive=receive,execute=execute)
        opts.update(updates)
        with patch("agent.operator_signed_execution.os.geteuid",return_value=0), \
             patch("agent.operator_signed_execution.PersistentStopGuard") as guard:
            guard.return_value.require_running.side_effect=lambda:self.events.append("stop")
            return execute_operator_signed_job(**opts)
    def test_signed_job_executes_once(self):
        self.assertEqual(self.invoke()["state"],"passed")
        self.assertEqual(self.events.count("execute"),1)
        self.assertLess(self.events.index("sign"),self.events.index("execute"))
    def test_unexpected_key_path_blocks(self):
        self.job["signing_key_file"]="/tmp/key"
        with self.assertRaises(PermissionError):
            self.invoke()
        self.assertNotIn("sign",self.events)
    def test_signer_rejection_blocks_executor(self):
        with self.assertRaises(PermissionError):
            self.invoke(receive=lambda **kw:{"state":"blocked"})
        self.assertNotIn("execute",self.events)
    def test_failed_execution_not_retried(self):
        result=self.invoke(execute=lambda **kw:{"state":"failed","cleanup_verified":False})
        self.assertEqual(result["state"],"blocked")
    def test_nonroot_rejected(self):
        with patch("agent.operator_signed_execution.os.geteuid",return_value=995):
            with self.assertRaises(PermissionError):
                execute_operator_signed_job(job_id="job1")
