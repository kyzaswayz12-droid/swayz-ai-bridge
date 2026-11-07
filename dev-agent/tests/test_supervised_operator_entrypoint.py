import unittest
from unittest.mock import patch
from agent.supervised_operator_entrypoint import verify_prepared_offline_job, main

class SupervisedOperatorEntrypointTests(unittest.TestCase):
    def test_nonroot_denied_before_window(self):
        with patch("agent.supervised_operator_entrypoint.os.geteuid",return_value=995):
            with self.assertRaises(PermissionError):
                main(["--job","job1"])
    def test_missing_metadata_fails_closed(self):
        with patch("agent.supervised_operator_entrypoint.require_engaged_stop"), \
             patch("agent.supervised_operator_entrypoint.load_protected_job",
                   side_effect=PermissionError("missing")):
            with self.assertRaises(PermissionError):
                verify_prepared_offline_job("job1")
    def test_unexpected_metadata_paths_rejected(self):
        with patch("agent.supervised_operator_entrypoint.require_engaged_stop"), \
             patch("agent.supervised_operator_entrypoint.load_protected_job",
                   return_value={"queue_db":"/tmp/forged"}):
            with self.assertRaises(PermissionError):
                verify_prepared_offline_job("job1")
    def test_entrypoint_passes_only_verified_job_to_window(self):
        calls=[]
        def window(**kw):
            calls.append(kw)
            return {"state":"passed","cleanup_verified":True}
        with patch("agent.supervised_operator_entrypoint.os.geteuid",return_value=0), \
             patch("agent.supervised_operator_entrypoint.run_supervised_window",side_effect=window):
            self.assertEqual(main(["--job","job1"]),0)
        self.assertEqual(calls[0]["job_id"],"job1")
        self.assertEqual(calls[0]["stop_db"],"/var/lib/swayzcontrol/state/stop.db")
    def test_blocked_execution_exit_nonzero(self):
        with patch("agent.supervised_operator_entrypoint.os.geteuid",return_value=0), \
             patch("agent.supervised_operator_entrypoint.run_supervised_window",
                   return_value={"state":"blocked","cleanup_verified":False}):
            self.assertEqual(main(["--job","job1"]),1)
