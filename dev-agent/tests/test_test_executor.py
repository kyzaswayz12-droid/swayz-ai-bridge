import subprocess
import tempfile
import unittest
from pathlib import Path
from agent.test_sandbox import build_test_invocation,TestInvocation
from agent.test_executor import run_tests

IMAGE="python:3.12.7-slim-bookworm@sha256:"+"a"*64

class TestExecutorTests(unittest.TestCase):
    def test_success_and_failure(self):
        with tempfile.TemporaryDirectory() as d:
            invocation=build_test_invocation(str(Path(d).resolve()),image=IMAGE)
            ok=run_tests(invocation,image=IMAGE,executor=lambda argv,**kwargs:
                subprocess.CompletedProcess(argv,0,"OK",""))
            self.assertTrue(ok.passed)
            failed=run_tests(invocation,image=IMAGE,executor=lambda argv,**kwargs:
                subprocess.CompletedProcess(argv,1,"FAILED",""))
            self.assertFalse(failed.passed)

    def test_timeout_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            invocation=build_test_invocation(str(Path(d).resolve()),image=IMAGE)
            def timeout(argv,**kwargs):
                raise subprocess.TimeoutExpired(argv,kwargs["timeout"])
            result=run_tests(invocation,image=IMAGE,executor=timeout)
            self.assertTrue(result.timed_out)
            self.assertFalse(result.passed)

    def test_modified_command_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            invocation=build_test_invocation(str(Path(d).resolve()),image=IMAGE)
            modified=TestInvocation(invocation.argv+("--privileged",),invocation.workspace)
            with self.assertRaises(ValueError):
                run_tests(modified,image=IMAGE,executor=lambda argv,**kwargs:None)

    def test_missing_docker_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            invocation=build_test_invocation(str(Path(d).resolve()),image=IMAGE)
            def unavailable(argv,**kwargs):
                raise FileNotFoundError("docker")
            self.assertFalse(run_tests(invocation,image=IMAGE,executor=unavailable).passed)
