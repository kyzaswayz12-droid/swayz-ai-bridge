import unittest
from agent.offline_end_to_end import run_demo

class OfflineEndToEndTests(unittest.TestCase):
    def test_signed_handoff_and_duplicate_rejection(self):
        result=run_demo()
        self.assertEqual(result["state"],"handoff_verified")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["duplicate_accepted"])
        self.assertEqual(result["staged_files"],1)
        self.assertFalse(result["docker_executed"])
        self.assertEqual(result["provider_calls"],0)
