"""CI gates for the real-UID offline handoff runner; never execute as root in CI."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"deployment/swayz_real_account_offline_handoff.py"


class RealAccountOfflineHandoffGates(unittest.TestCase):
    def run_script(self,*flags):
        env={**os.environ,"PYTHONPATH":str(SCRIPT.parent.parent),
             "PYTHONDONTWRITEBYTECODE":"1"}
        return subprocess.run([sys.executable,"-B",str(SCRIPT),*flags],
                              env=env,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,text=True,timeout=8)

    def test_help_has_only_offline_test_switch(self):
        result=self.run_script("--help")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("--offline-test",result.stdout)
        self.assertNotIn("--execute-paid",result.stdout)
        self.assertNotIn("--issue-and-publish",result.stdout)

    def test_no_flag_fails_closed(self):
        result=self.run_script()
        self.assertNotEqual(result.returncode,0)
        self.assertIn("Disabled by default",result.stderr)

    def test_unknown_live_flag_is_rejected(self):
        result=self.run_script("--execute-paid")
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn("REAL_UID_ONE_SHOT_PASS",result.stdout)

    def test_explicit_offline_flag_has_no_authority_as_nonroot(self):
        from unittest.mock import patch
        from deployment.swayz_real_account_offline_handoff import _run
        with patch("deployment.swayz_real_account_offline_handoff.os.geteuid",
                   return_value=1001):
            with self.assertRaises(PermissionError):
                _run()


if __name__=="__main__":
    unittest.main()
