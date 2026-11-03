"""Offline tests for conservative cleanup evidence, without Docker."""
import unittest
from agent.cleanup_evidence import cleanup_evidence_verified


class CleanupEvidenceTests(unittest.TestCase):
    def check(self, **changes):
        args = dict(container_name="swayz-test-job1", inspect_exit_code=1,
                    inspect_stderr="Error: No such object: swayz-test-job1",
                    daemon_healthy=True)
        args.update(changes)
        return cleanup_evidence_verified(**args)

    def test_expected_absence_evidence(self):
        self.assertTrue(self.check())

    def test_daemon_unhealthy_rejected(self):
        self.assertFalse(self.check(daemon_healthy=False))

    def test_wrong_container_rejected(self):
        self.assertFalse(self.check(inspect_stderr="Error: No such object: other"))

    def test_generic_daemon_error_rejected(self):
        self.assertFalse(self.check(inspect_stderr="Error response from daemon: unavailable"))

    def test_nonzero_other_than_one_rejected(self):
        self.assertFalse(self.check(inspect_exit_code=125))

    def test_successful_inspect_is_not_absence(self):
        self.assertFalse(self.check(inspect_exit_code=0))

    def test_untrusted_container_name_rejected(self):
        self.assertFalse(self.check(container_name="unrelated"))

    def test_truthy_daemon_status_not_accepted(self):
        self.assertFalse(self.check(daemon_healthy=1))


if __name__ == "__main__":
    unittest.main()
