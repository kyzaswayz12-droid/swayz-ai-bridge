"""Disposable supervised Docker smoke test for CI or explicit local acceptance.

Runs a disposable, network-disabled, read-only container. No credentials,
external APIs, GitHub writes or production control database.
"""
import hashlib
import os
import sqlite3
import subprocess
import tempfile
import argparse
from pathlib import Path

from agent.worker_lifecycle import plan_worker_lifecycle
from agent.guarded_transport_factory import build_guarded_transport
from agent.supervised_lifecycle_adapter import run_supervised_lifecycle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--supervised-local-smoke", action="store_true")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" and not args.supervised_local_smoke:
        raise PermissionError("CI or explicit supervised local smoke only")
    if args.supervised_local_smoke and os.geteuid() == 0:
        raise PermissionError("Do not run the supervised smoke as root")
    digest_ref = subprocess.check_output(
        ["docker", "image", "inspect", "python:3.12-slim",
         "--format", "{{index .RepoDigests 0}}"], text=True, timeout=10).strip()
    if not digest_ref.startswith("python@sha256:"):
        raise RuntimeError("Immutable Python image digest unavailable")
    digest = digest_ref[len("python@"):]
    with tempfile.TemporaryDirectory(prefix="swayz-ci-") as temp:
        root = Path(temp)
        root.chmod(0o755)
        workspace = root / "job1"
        tests = workspace / "tests"
        tests.mkdir(parents=True)
        test_file = tests / "test_smoke.py"
        test_file.write_text(
            "import unittest\n"
            "class Smoke(unittest.TestCase):\n"
            "    def test_ok(self): self.assertEqual(2 + 2, 4)\n"
        )
        test_file.chmod(0o444)
        tests.chmod(0o555)
        workspace.chmod(0o555)
        db_path = root / "control.db"
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")
        plan = plan_worker_lifecycle("job1", digest, workspace=str(workspace))
        transport = build_guarded_transport(plan, server_control_db=str(db_path))
        result = run_supervised_lifecycle(
            plan, transport=transport, daemon_probe=transport.daemon_healthy)
        if result.state != "passed" or not result.cleanup_verified:
            # CI uses only disposable test data; report failure evidence without
            # relaxing cleanup checks or printing credentials.
            print("SWAYZ_CI_DOCKER_STATE", result.state)
            print("SWAYZ_CI_DOCKER_EXIT", result.exit_code)
            print("SWAYZ_CI_DOCKER_OUTPUT", result.output[:1500])
            inspect = subprocess.run(["docker", "inspect", plan.name],
                capture_output=True, text=True, timeout=10, check=False)
            print("SWAYZ_CI_INSPECT_EXIT", inspect.returncode)
            print("SWAYZ_CI_INSPECT_STDERR", repr(inspect.stderr[:500]))
            raise RuntimeError(f"Supervised Docker smoke failed: {result.state}")
        print("SWAYZ_SUPERVISED_DOCKER_SMOKE_PASSED")


if __name__ == "__main__":
    main()
