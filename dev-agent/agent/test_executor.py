"""Bounded execution wrapper for an independently restricted Docker worker.

This is NOT an authorisation to grant the AI process Docker socket access.
The trusted worker must run separately with narrow job permissions.
"""
from dataclasses import dataclass
import subprocess
from .test_sandbox import TestInvocation, build_test_invocation

@dataclass(frozen=True)
class TestResult:
    passed: bool
    returncode: int | None
    timed_out: bool
    output: str

def run_tests(invocation: TestInvocation, *, image: str,
              timeout_seconds: int = 120, executor=subprocess.run) -> TestResult:
    if type(timeout_seconds) is not int or not 10 <= timeout_seconds <= 300:
        raise ValueError("Invalid timeout")
    if not isinstance(invocation, TestInvocation):
        raise ValueError("Invalid invocation")
    # Reconstruct the entire command; never execute model-supplied argv.
    expected = build_test_invocation(invocation.workspace, image=image)
    if invocation != expected:
        raise ValueError("Test invocation differs from approved command")
    try:
        result = executor(list(expected.argv), capture_output=True, text=True,
                          timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        return TestResult(False, None, True, "Test deadline exceeded")
    except OSError:
        return TestResult(False, None, False, "Isolated worker unavailable")
    output = ((result.stdout or "") + "\n" + (result.stderr or ""))[:12000]
    return TestResult(result.returncode == 0, result.returncode, False, output)
