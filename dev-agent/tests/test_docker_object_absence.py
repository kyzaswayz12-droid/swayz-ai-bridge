import unittest
from types import SimpleNamespace
from agent.supervised_docker_executor import _confirmed_absent


class DockerObjectAbsenceTests(unittest.TestCase):
    def test_named_missing_container(self):
        result = SimpleNamespace(returncode=1, stdout="",
                                 stderr="Error: No such object: swayz-test-job1")
        self.assertTrue(_confirmed_absent(result, "swayz-test-job1"))

    def test_daemon_failure_not_absence(self):
        result = SimpleNamespace(returncode=1, stdout="",
                                 stderr="Cannot connect to Docker daemon")
        self.assertFalse(_confirmed_absent(result, "swayz-test-job1"))

    def test_other_container_not_absence(self):
        result = SimpleNamespace(returncode=1, stdout="",
                                 stderr="Error: No such object: swayz-test-other")
        self.assertFalse(_confirmed_absent(result, "swayz-test-job1"))
