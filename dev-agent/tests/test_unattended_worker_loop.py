import unittest
from agent.unattended_worker_loop import run_worker_loop

class UnattendedWorkerLoopTests(unittest.TestCase):
    def test_empty_then_one_completed_draft(self):
        outcomes=iter([{"state":"empty"},{"state":"done","draft_pr":{"draft":True}}])
        seen=[]
        result=run_worker_loop(require_running=lambda:None,
            run_one_cycle=lambda:next(outcomes),
            shutdown_requested=lambda:False,
            sleep=lambda seconds:seen.append(seconds),max_cycles=1)
        self.assertEqual(result,{"state":"cycle_limit","processed":1})
        self.assertEqual(seen,[15])

    def test_blocked_job_halts_without_retry(self):
        calls=[]
        def cycle():
            calls.append(1)
            return {"state":"blocked"}
        result=run_worker_loop(require_running=lambda:None,
            run_one_cycle=cycle,shutdown_requested=lambda:False,
            sleep=lambda _:None)
        self.assertEqual(result,{"state":"blocked","processed":1})
        self.assertEqual(len(calls),1)

    def test_missing_draft_halts(self):
        with self.assertRaises(PermissionError):
            run_worker_loop(require_running=lambda:None,
                run_one_cycle=lambda:{"state":"done","draft_pr":None},
                shutdown_requested=lambda:False,sleep=lambda _:None)

    def test_stop_prevents_job(self):
        calls=[]
        def stopped():
            raise PermissionError("Stop engaged")
        with self.assertRaises(PermissionError):
            run_worker_loop(require_running=stopped,
                run_one_cycle=lambda:calls.append(1),
                shutdown_requested=lambda:False,sleep=lambda _:None)
        self.assertEqual(calls,[])

    def test_shutdown_prevents_job(self):
        calls=[]
        result=run_worker_loop(require_running=lambda:None,
            run_one_cycle=lambda:calls.append(1),
            shutdown_requested=lambda:True,sleep=lambda _:None)
        self.assertEqual(result,{"state":"stopped","processed":0})
        self.assertEqual(calls,[])

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            run_worker_loop(require_running=lambda:None,
                run_one_cycle=lambda:None,shutdown_requested=lambda:False,
                max_cycles=21)
