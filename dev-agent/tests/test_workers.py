import unittest
from agent.core import TaskStore
from agent.workers import Proposal,Review,demo,process_one

class WorkerTests(unittest.TestCase):
    def test_mock_workflow_waits_for_approval(self):
        store=TaskStore()
        store.enqueue("task1","Improve paper risk limits")
        result=demo(store)
        self.assertEqual(result["state"],"approval_required")
        self.assertEqual(store.status(),{"approval_required":1})
        self.assertIsNone(demo(store))
        store.close()

    def test_mismatched_review_blocks_task(self):
        store=TaskStore()
        store.enqueue("task2","Review portfolio valuations")
        with self.assertRaisesRegex(ValueError,"does not match"):
            process_one(store,lambda task_id,title:"safe proposal",
                lambda proposal:Review("0"*64,True,"wrong fingerprint"))
        self.assertEqual(store.status(),{"blocked":1})
        store.close()

    def test_rejection_blocks_task(self):
        store=TaskStore()
        store.enqueue("task3","Review code")
        result=process_one(store,lambda task_id,title:"candidate",
            lambda proposal:Review(proposal.sha256,False,"Rejected"))
        self.assertEqual(result["state"],"blocked")
        store.close()

    def test_coder_failure_blocks_task(self):
        store=TaskStore()
        store.enqueue("task4","Review code")
        def broken(task_id,title):
            raise RuntimeError("worker unavailable")
        with self.assertRaises(RuntimeError):
            process_one(store,broken,lambda proposal:None)
        self.assertEqual(store.status(),{"blocked":1})
        store.close()
