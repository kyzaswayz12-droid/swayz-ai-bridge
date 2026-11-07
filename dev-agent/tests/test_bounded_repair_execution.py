import unittest
from agent.bounded_repair_execution import run_one_authorised_repair

class BoundedRepairExecutionTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.args=dict(original_job_id="original",repair_job_id="repair1",
            failed_result={"state":"failed","cleanup_verified":True},
            approved_repair={"job_id":"repair1","proposal_sha256":"a"*64,
                             "base_sha":"b"*40},
            require_running=lambda:None,execute_repair=self.execute)

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return {"state":"passed","cleanup_verified":True}

    def invoke(self, **updates):
        args=dict(self.args);args.update(updates)
        return run_one_authorised_repair(**args)

    def test_single_approved_repair(self):
        self.assertEqual(self.invoke(),{"state":"passed","repair_attempts":1})
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0]["job_id"],"repair1")

    def test_original_job_cannot_be_replayed(self):
        with self.assertRaises(PermissionError):
            self.invoke(repair_job_id="original")
        self.assertEqual(self.calls,[])

    def test_uncertain_cleanup_blocks_repair(self):
        with self.assertRaises(PermissionError):
            self.invoke(failed_result={"state":"failed","cleanup_verified":False})
        self.assertEqual(self.calls,[])

    def test_unapproved_repair_blocks_execution(self):
        with self.assertRaises(PermissionError):
            self.invoke(approved_repair={})
        self.assertEqual(self.calls,[])

    def test_failed_repair_never_retries(self):
        result=self.invoke(execute_repair=lambda **kw:{"state":"failed","cleanup_verified":True})
        self.assertEqual(result,{"state":"blocked","repair_attempts":1})

    def test_stop_blocks_execution(self):
        def stop():
            raise PermissionError("Stopped")
        with self.assertRaises(PermissionError):
            self.invoke(require_running=stop)
        self.assertEqual(self.calls,[])
