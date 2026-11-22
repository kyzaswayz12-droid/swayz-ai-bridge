"""Operator-facing grant and provider CLIs stay inert without explicit flags."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"deployment"
SCRIPTS=("swayz_provider_grant_operator.py","swayz_provider_worker_one_shot.py")


class ProviderCliGateTests(unittest.TestCase):
    def call(self, filename, *args):
        return subprocess.run(
            [sys.executable,str(ROOT/filename),*args],
            text=True,capture_output=True,timeout=8,
            env={**os.environ,"PYTHONPATH":str(ROOT.parent)})

    def test_help_is_read_only(self):
        for name in SCRIPTS:
            with self.subTest(name=name):
                result=self.call(name,"--help")
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn("--job",result.stdout)

    def test_operator_grant_is_disabled_without_issue_flag(self):
        result=self.call(SCRIPTS[0],"--job","ci-gate-only",
                         "--base-sha","a"*40)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("--issue-and-publish",result.stderr)

    def test_paid_worker_disabled_without_explicit_flag(self):
        result=self.call(SCRIPTS[1],"--job","ci-gate-only",
                         "--base-sha","a"*40)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("--execute-paid",result.stderr)


if __name__=="__main__":
    unittest.main()
