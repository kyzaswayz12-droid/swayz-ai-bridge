import unittest
from unittest.mock import patch
from agent.authorised_development_worker import run_authorised_development_worker

class AuthorisedDevelopmentWorkerTests(unittest.TestCase):
    def test_delegates_to_existing_bounded_pipeline(self):
        calls=[]
        with patch("agent.authorised_development_worker.run_one_bounded_provider_queue_cycle",
                   side_effect=lambda **kw: (calls.append(kw) or
                        {"state":"done","draft_pr":{"draft":True}})):
            result=run_authorised_development_worker(
                require_running=lambda:None,shutdown_requested=lambda:False,
                run_primary=lambda **kw:None,prepare_repair=lambda **kw:None,
                run_repair=lambda **kw:None,
                queue_options={"owner_approved":True,"paid_calls_enabled":True},
                sleep=lambda _:None,max_cycles=1)
        self.assertEqual(result["processed"],1)
        self.assertEqual(len(calls),1)

    def test_unapproved_paid_calls_rejected(self):
        with self.assertRaises(PermissionError):
            run_authorised_development_worker(
                require_running=lambda:None,shutdown_requested=lambda:False,
                run_primary=lambda **kw:None,prepare_repair=lambda **kw:None,
                run_repair=lambda **kw:None,
                queue_options={"owner_approved":True,"paid_calls_enabled":False},
                sleep=lambda _:None,max_cycles=1)

    def test_conflicting_stop_authority_rejected(self):
        with self.assertRaises(PermissionError):
            run_authorised_development_worker(
                require_running=lambda:None,shutdown_requested=lambda:False,
                run_primary=lambda **kw:None,prepare_repair=lambda **kw:None,
                run_repair=lambda **kw:None,
                queue_options={"owner_approved":True,"paid_calls_enabled":True,
                               "require_running":lambda:None},
                sleep=lambda _:None,max_cycles=1)
