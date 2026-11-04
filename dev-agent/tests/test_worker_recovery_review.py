import unittest
from agent.worker_recovery_review import review_worker_recovery


class WorkerRecoveryReviewTests(unittest.TestCase):
    def review(self, **changes):
        args = dict(job_id="job1", journal_state="running",
                    inspect_exit_code=1,
                    inspect_stderr="Error: No such object: swayz-test-job1",
                    daemon_healthy=True)
        args.update(changes)
        return review_worker_recovery(**args)

    def test_verified_absence_still_blocks_reexecution(self):
        decision = self.review()
        self.assertTrue(decision.cleanup_verified)
        self.assertEqual(decision.state, "blocked")
        self.assertFalse(decision.execution_allowed)

    def test_unhealthy_daemon_cannot_confirm_cleanup(self):
        decision = self.review(daemon_healthy=False)
        self.assertFalse(decision.cleanup_verified)
        self.assertFalse(decision.execution_allowed)

    def test_unexpected_job_state_rejected(self):
        with self.assertRaises(PermissionError):
            self.review(journal_state="passed")

    def test_incorrect_container_identity_rejected(self):
        decision = self.review(inspect_stderr="Error: No such object: swayz-test-other")
        self.assertFalse(decision.cleanup_verified)

    def test_admitted_job_not_automatically_executed(self):
        decision = self.review(journal_state="admitted")
        self.assertEqual(decision.state, "blocked")
        self.assertFalse(decision.execution_allowed)
