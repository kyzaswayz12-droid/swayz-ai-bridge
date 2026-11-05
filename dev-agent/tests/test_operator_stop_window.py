import unittest
from unittest.mock import patch
from agent.operator_stop_window import open_supervised_window

class OperatorStopWindowTests(unittest.TestCase):
    def args(self):
        return dict(job_id="job1",confirmation="AUTHORISE SUPERVISED job1",
                    watchdog_script="/opt/swayz/executor-app/deployment/swayz_supervised_smoke.py")

    @patch("agent.operator_stop_window.os.geteuid",return_value=1000)
    def test_nonroot_rejected(self, root):
        with self.assertRaises(PermissionError):
            open_supervised_window(**self.args())

    @patch("agent.operator_stop_window.sys.stdin.isatty",return_value=False)
    @patch("agent.operator_stop_window.os.geteuid",return_value=0)
    def test_noninteractive_rejected(self, root, tty):
        with self.assertRaises(PermissionError):
            open_supervised_window(**self.args())

    @patch("agent.operator_stop_window.sys.stdin.isatty",return_value=True)
    @patch("agent.operator_stop_window.os.geteuid",return_value=0)
    def test_wrong_confirmation_rejected(self, root, tty):
        args=self.args()
        args["confirmation"]="yes"
        with self.assertRaises(PermissionError):
            open_supervised_window(**args)

    @patch("agent.operator_stop_window.sys.stdin.isatty",return_value=True)
    @patch("agent.operator_stop_window.os.geteuid",return_value=0)
    def test_unpinned_watchdog_rejected(self, root, tty):
        args=self.args()
        args["watchdog_script"]="/tmp/recover.py"
        with self.assertRaises(PermissionError):
            open_supervised_window(**args)

    @patch("agent.operator_stop_window.sys.stdin.isatty",return_value=True)
    @patch("agent.operator_stop_window.os.geteuid",return_value=0)
    def test_invalid_job_rejected(self, root, tty):
        args=self.args()
        args["job_id"]="../bad"
        with self.assertRaises(ValueError):
            open_supervised_window(**args)
