"""Restricted local Docker command transport for supervised worker testing.

Not a remote endpoint or autonomous service. Call only after independently
validating signed provenance, journal admission, budget, stop and fixed plan.
The caller must not expose this transport to untrusted Python code.
"""
import subprocess
from .worker_lifecycle import WorkerLifecycle, plan_worker_lifecycle


class FixedDockerTransport:
    """Execute only the three fixed commands for a single validated lifecycle."""

    def __init__(self, plan: WorkerLifecycle, *, require_running):
        if not callable(require_running):
            raise PermissionError("Authoritative stop check required")
        if not isinstance(plan, WorkerLifecycle) or plan.executes:
            raise PermissionError("Invalid worker lifecycle")
        if not plan.name.startswith("swayz-test-"):
            raise PermissionError("Invalid worker identity")
        job_id = plan.name.removeprefix("swayz-test-")
        image = next((v for v in plan.run_argv if v.startswith("python@sha256:")), None)
        if image is None:
            raise PermissionError("Missing approved image digest")
        # Independently rebuild the fixed lifecycle, including mount and timeout.
        mount = next((v for v in plan.run_argv if v.startswith("type=bind,src=")), None)
        if mount is None or not mount.endswith(",dst=/work,readonly"):
            raise PermissionError("Read-only workspace required")
        workspace = mount[len("type=bind,src="):-len(",dst=/work,readonly")]
        expected = plan_worker_lifecycle(
            job_id, image[len("python@"):], workspace=workspace,
            timeout_seconds=plan.timeout_seconds)
        if plan != expected:
            raise PermissionError("Docker command differs from fixed policy")
        self.plan = plan
        self.require_running = require_running
        self._run_attempted = False
        self.allowed = (plan.run_argv, plan.kill_argv, plan.inspect_argv)

    def __call__(self, argv, *, capture_output, text, timeout, check):
        if not isinstance(argv, list) or tuple(argv) not in self.allowed:
            raise PermissionError("Unapproved Docker command")
        if capture_output is not True or text is not True or check is not False:
            raise PermissionError("Unapproved subprocess settings")
        maximum = self.plan.timeout_seconds if tuple(argv) == self.plan.run_argv else 10
        if type(timeout) is not int or timeout < 1 or timeout > maximum:
            raise PermissionError("Unapproved command timeout")
        if tuple(argv) == self.plan.run_argv:
            if self._run_attempted:
                raise PermissionError("Worker run command cannot be replayed")
            # The stop check is mandatory immediately before the only run.
            self.require_running()
            self._run_attempted = True
        elif not self._run_attempted:
            raise PermissionError("Cleanup commands require a prior run attempt")
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            check=False, stdin=subprocess.DEVNULL)

    def daemon_healthy(self):
        """Probe Docker separately; never treat an inspect error as proof."""
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=5,
                check=False, stdin=subprocess.DEVNULL)
            return result.returncode == 0 and bool(result.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            return False
