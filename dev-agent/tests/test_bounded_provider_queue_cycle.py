import unittest
from unittest.mock import patch
from agent.bounded_provider_queue_cycle import run_one_bounded_provider_queue_cycle

class BoundedProviderQueueCompositionTests(unittest.TestCase):
    def test_composes_existing_bounded_runner_and_queue(self):
        captured=[]
        def primary(**kw):
            captured.append("primary")
            return {"state":"passed","cleanup_verified":True}
        with patch("agent.bounded_provider_queue_cycle.run_next_provider_cycle") as cycle:
            def exercise(**kw):
                result=kw["run_verified_tests"](job_id="j1",plan=object())
                self.assertEqual(result["state"],"passed")
                return {"state":"done"}
            cycle.side_effect=exercise
            result=run_one_bounded_provider_queue_cycle(
                run_primary=primary,prepare_repair=lambda **kw:None,
                run_repair=lambda **kw:None,require_running=lambda:None)
            self.assertEqual(result["state"],"done")
            self.assertEqual(captured,["primary"])

    def test_missing_repair_authority_fails_closed(self):
        with self.assertRaises(PermissionError):
            run_one_bounded_provider_queue_cycle(
                run_primary=lambda **kw:None,prepare_repair=None,
                run_repair=lambda **kw:None,require_running=lambda:None)
