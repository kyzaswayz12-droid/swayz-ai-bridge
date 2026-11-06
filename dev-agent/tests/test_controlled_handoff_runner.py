import unittest
from agent.controlled_handoff_runner import run_controlled_handoff

class ControlledHandoffTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        self.result={"state":"passed","cleanup_verified":True}
        self.journal=("passed",0,"ok")
    def run(self, **overrides):
        def cb(name, value):
            def inner(**kwargs):
                self.events.append(name)
                return value
            return inner
        opts=dict(job_id="job1",require_running=cb("stop",None),
            verify_authority=cb("authority",True),
            prepare_authorised_job=cb("admit",{"state":"admitted","job_id":"job1"}),
            sign_prepared_job=cb("sign",{"state":"admitted","job_id":"job1"}),
            run_trusted_executor=cb("execute",self.result),
            journal_status=cb("journal",self.journal))
        opts.update(overrides)
        return run_controlled_handoff(**opts)
    def test_verified_execution(self):
        self.assertEqual(self.run()["state"],"passed")
        self.assertEqual(self.events.count("execute"),1)
    def test_missing_authority_never_admits(self):
        with self.assertRaises(PermissionError):
            self.run(verify_authority=lambda **kw:False)
        self.assertNotIn("admit",self.events)
    def test_invalid_admission_never_signs(self):
        with self.assertRaises(PermissionError):
            self.run(prepare_authorised_job=lambda **kw:{"state":"queued"})
        self.assertNotIn("sign",self.events)
    def test_signer_failure_never_executes(self):
        with self.assertRaises(PermissionError):
            self.run(sign_prepared_job=lambda **kw:{"state":"blocked"})
        self.assertNotIn("execute",self.events)
    def test_uncertain_cleanup_blocks(self):
        self.result={"state":"passed","cleanup_verified":False}
        self.assertEqual(self.run()["state"],"blocked")
    def test_journal_mismatch_blocks(self):
        self.journal=("running",None,"")
        self.assertEqual(self.run()["state"],"blocked")
    def test_invalid_job_never_checks_authority(self):
        with self.assertRaises(PermissionError):
            self.run(job_id="../unsafe")
        self.assertEqual(self.events,[])
