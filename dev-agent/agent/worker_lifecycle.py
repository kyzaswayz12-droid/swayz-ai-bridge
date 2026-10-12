"""Offline trusted-worker execution lifecycle planner.

This module deliberately never calls Docker. The privileged worker must
separately validate provenance and run the planned commands.
"""
from dataclasses import dataclass
import re

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")


@dataclass(frozen=True)
class WorkerLifecycle:
    name: str
    run_argv: tuple[str, ...]
    kill_argv: tuple[str, ...]
    inspect_argv: tuple[str, ...]
    timeout_seconds: int
    executes: bool = False


def plan_worker_lifecycle(job_id: str, image_digest: str, *,
                          timeout_seconds: int = 120) -> WorkerLifecycle:
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise ValueError("Invalid job ID")
    if not isinstance(image_digest, str) or not _DIGEST.fullmatch(image_digest):
        raise ValueError("Invalid image digest")
    if image_digest == "sha256:" + "0" * 64:
        raise ValueError("Placeholder image digest forbidden")
    if type(timeout_seconds) is not int or not 10 <= timeout_seconds <= 300:
        raise ValueError("Invalid worker timeout")
    name = "swayz-test-" + job_id
    image = "python@"+image_digest
    return WorkerLifecycle(
        name=name,
        run_argv=(
            "docker", "run", "--name", name, "--rm",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "64", "--memory", "512m", "--cpus", "1",
            "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m",
            image, "python", "-m", "unittest", "discover", "-s", "tests", "-v"
        ),
        kill_argv=("docker", "kill", name),
        inspect_argv=("docker", "inspect", name),
        timeout_seconds=timeout_seconds
    )
