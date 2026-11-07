import unittest
from types import SimpleNamespace
from agent.bounded_cycle_runner import bounded_test_runner

class BoundedCycleRunnerTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        self.plan=SimpleNamespace(base_sha="a"*40,proposal_sha256="b"*64)

    def invoke(self, primary, repair=None):
        def first(**kwargs):
            self.events.append("primary")
            return primary
        def prepare(**kwargs):
            self.events.append("prepare")
            return {"repair_job_id":"repair1",
                    "approved_repair":{"job_id":"repair1",
                                       "proposal_sha256":"c"*64,
                                       "base_sha":"a"*40},
                    "repair_delivery":{"raw_plan":"reviewed-plan",
                        "review_response":"reviewed-response",
                        "proposal_sha256":"c"*64}}
        def second(**kwargs):
            self.events.append("repair")
            return repair
        return bounded_test_runner(
            job_id="job1",plan=self.plan,run_primary=first,
            prepare_repair=prepare,run_repair=second,
            require_running=lambda:None)

    def test_primary_pass_never_repairs(self):
        result=self.invoke({"state":"passed","cleanup_verified":True})
        self.assertEqual(result["state"],"passed")
        self.assertEqual(self.events,["primary"])

    def test_failed_primary_gets_exactly_one_repair(self):
        result=self.invoke({"state":"failed","cleanup_verified":True},
                        {"state":"passed","cleanup_verified":True})
        self.assertEqual(result["state"],"passed")
        self.assertEqual(result["repair_delivery"]["proposal_sha256"],"c"*64)
        self.assertEqual(self.events,["primary","prepare","repair"])

    def test_failed_repair_blocks_without_retry(self):
        result=self.invoke({"state":"failed","cleanup_verified":True},
                        {"state":"failed","cleanup_verified":True})
        self.assertEqual(result["state"],"blocked")
        self.assertEqual(self.events,["primary","prepare","repair"])

    def test_uncertain_cleanup_never_repairs(self):
        result=self.invoke({"state":"failed","cleanup_verified":False})
        self.assertEqual(result["state"],"blocked")
        self.assertEqual(self.events,["primary"])

    def test_missing_trusted_preparation_rejected(self):
        with self.assertRaises(PermissionError):
            bounded_test_runner(job_id="job1",plan=self.plan,
                run_primary=lambda **kw:{"state":"failed","cleanup_verified":True},
                prepare_repair=None,run_repair=lambda **kw:None,
                require_running=lambda:None)
