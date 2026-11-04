import unittest
from types import SimpleNamespace
from unittest.mock import patch
from agent.supervised_integration import simulate_supervised_integration


class TestTransport:
    swayz_test_double = True
    def __call__(self, *args, **kwargs):
        raise AssertionError("Not expected in mocked integration")


class TestProbe:
    swayz_test_double = True
    def __call__(self):
        return True


class SupervisedIntegrationTests(unittest.TestCase):
    @patch("agent.supervised_integration.run_supervised_lifecycle")
    @patch("agent.supervised_integration.validate_reserved_signed_worker_plan")
    def test_valid_gate_reaches_supervised_adapter(self, gate, adapter):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=False))
        adapter.return_value = SimpleNamespace(state="passed", cleanup_verified=True)
        result = simulate_supervised_integration(
            job_id="job1", test_transport=TestTransport(),
            test_daemon_probe=TestProbe())
        self.assertEqual(result.state, "passed")
        self.assertFalse(result.production_enabled)
        gate.assert_called_once_with(job_id="job1")
        adapter.assert_called_once()

    @patch("agent.supervised_integration.run_supervised_lifecycle")
    @patch("agent.supervised_integration.validate_reserved_signed_worker_plan")
    def test_gate_failure_never_reaches_adapter(self, gate, adapter):
        gate.side_effect = PermissionError("stop engaged")
        with self.assertRaises(PermissionError):
            simulate_supervised_integration(
                job_id="job1", test_transport=TestTransport(),
                test_daemon_probe=TestProbe())
        adapter.assert_not_called()

    @patch("agent.supervised_integration.validate_reserved_signed_worker_plan")
    def test_real_callable_without_marker_rejected(self, gate):
        with self.assertRaises(PermissionError):
            simulate_supervised_integration(
                job_id="job1", test_transport=lambda *a, **k: None,
                test_daemon_probe=TestProbe())
        gate.assert_not_called()

    @patch("agent.supervised_integration.validate_reserved_signed_worker_plan")
    def test_missing_probe_rejected(self, gate):
        with self.assertRaises(PermissionError):
            simulate_supervised_integration(
                job_id="job1", test_transport=TestTransport())
        gate.assert_not_called()

    @patch("agent.supervised_integration.run_supervised_lifecycle")
    @patch("agent.supervised_integration.validate_reserved_signed_worker_plan")
    def test_executable_plan_rejected(self, gate, adapter):
        gate.return_value = SimpleNamespace(lifecycle=SimpleNamespace(executes=True))
        with self.assertRaises(PermissionError):
            simulate_supervised_integration(
                job_id="job1", test_transport=TestTransport(),
                test_daemon_probe=TestProbe())
        adapter.assert_not_called()
