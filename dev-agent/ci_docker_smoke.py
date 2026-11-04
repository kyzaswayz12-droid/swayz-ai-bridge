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
from agent.change_plan import ApprovedPlan, Change
from agent.generated_code_docker_adapter import run_generated_code_tests


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
        # Execute a generated test file through the SAME restricted Docker
        # lifecycle. This proves the proposed bytes, not a static fixture,
        # are actually exercised before any draft PR could be published.
        staging = root / "generated-staging"
        snapshots = root / "generated-snapshots"
        staging.mkdir(mode=0o755)
        snapshots.mkdir(mode=0o755)
        generated_plan = ApprovedPlan(
            "a" * 40, "b" * 64, "agent/generated-smoke",
            (Change("tests/test_generated.py",
                "import unittest\nclass Generated(unittest.TestCase):\n"
                "    def test_generated(self): self.assertEqual(6 * 7, 42)\n"),))
        def execute_generated(*, job_id, snapshot, snapshot_root, expected_hashes):
            plan = plan_worker_lifecycle(job_id, digest, workspace=snapshot)
            adapter = build_guarded_transport(plan, server_control_db=str(db_path))
            actual = run_supervised_lifecycle(
                plan, transport=adapter, daemon_probe=adapter.daemon_healthy)
            if actual.state != "passed":
                print("SWAYZ_GENERATED_DOCKER_STATE", actual.state)
                print("SWAYZ_GENERATED_DOCKER_EXIT", actual.exit_code)
                print("SWAYZ_GENERATED_DOCKER_OUTPUT", actual.output[:1500])
            return {"state": actual.state, "cleanup_verified": actual.cleanup_verified}
        generated = run_generated_code_tests(
            job_id="generated1", plan=generated_plan,
            staging_root=str(staging), snapshot_root=str(snapshots),
            require_running=lambda: None, trusted_execute=execute_generated)
        if generated != {"state": "passed", "cleanup_verified": True}:
            raise RuntimeError("Generated code did not pass real Docker acceptance")
        print("SWAYZ_GENERATED_CODE_REAL_DOCKER_PASSED")
        # Verify the same persistent stop database prevents a second real
        # Docker invocation. The second job is never launched.
        with sqlite3.connect(db_path) as db:
            db.execute("UPDATE agent_control SET stopped=1 WHERE id=1")
        blocked_workspace = root / "job2"
        blocked_workspace.mkdir(mode=0o555)
        blocked_workspace.chmod(0o555)
        blocked_plan = plan_worker_lifecycle("job2", digest, workspace=str(blocked_workspace))
        try:
            blocked_transport = build_guarded_transport(
                blocked_plan, server_control_db=str(db_path))
        except PermissionError:
            pass
        else:
            raise RuntimeError("Emergency stop failed to block new job")
        absent = subprocess.run(
            ["docker", "inspect", blocked_plan.name],
            capture_output=True, text=True, timeout=10, check=False)
        if absent.returncode != 1 or "no such object" not in absent.stderr.lower():
            raise RuntimeError("Blocked job container absence unverified")
        print("SWAYZ_CI_STOP_BLOCKS_NEW_DOCKER_JOB")
        print("SWAYZ_SUPERVISED_DOCKER_SMOKE_PASSED")


if __name__ == "__main__":
    main()
