import unittest
from agent.collaboration_cost_preview import preview_task

class CollaborationCostPreviewTests(unittest.TestCase):
    def test_preview_is_nonzero_and_not_provider_cap(self):
        result=preview_task("Review automated trading risk-control tests")
        self.assertGreater(result.total_reservation_usd,0)
        self.assertEqual(result.total_reservation_usd,
                         result.openai_reservation_usd+result.claude_reservation_usd)
        self.assertFalse(result.is_provider_hard_cap)
    def test_large_task_rejected(self):
        with self.assertRaises(ValueError):
            preview_task("x"*4097)
    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):
            preview_task("Check tests",openai_model="unknown")
