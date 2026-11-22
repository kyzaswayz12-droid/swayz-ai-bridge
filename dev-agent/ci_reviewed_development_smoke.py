"""CI-only end-to-end reviewed code task: fake model outputs, REAL isolated Docker.

No provider requests, GitHub API writes, admission ledger or production stop changes.
This exercises the existing review -> generated snapshot -> Docker -> draft workflow.
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from agent.development_task_intake import DevelopmentTaskQueue
from agent.generated_code_docker_adapter import run_generated_code_tests
from agent.guarded_transport_factory import build_guarded_transport
from agent.supervised_lifecycle_adapter import run_supervised_lifecycle
from agent.worker_lifecycle import plan_worker_lifecycle
from agent.supervised_development_cycle import complete_supervised_cycle


BASE = "a" * 40
JOB = "ci-reviewed-code-1"
REPO = "kyzaswayz12-droid/swayz-ai-bridge"

# The concrete code-development task. This is executed in Docker, not just
# marked successful by a test double.
GENERATED_TEST = (
    "import re\n"
    "import unittest\n"
    "def normalise_job_label(label):\n"
    "    if not isinstance(label, str) or not re.fullmatch(r'[a-z0-9-]{1,32}', label):\n"
    "        raise ValueError('invalid job label')\n"
    "    return label.lower()\n"
    "class LabelTests(unittest.TestCase):\n"
    "    def test_valid(self): self.assertEqual(normalise_job_label('safe-job-1'), 'safe-job-1')\n"
    "    def test_reject_spaces(self):\n"
    "        with self.assertRaises(ValueError): normalise_job_label('unsafe job')\n"
    "    def test_reject_symbols(self):\n"
    "        with self.assertRaises(ValueError): normalise_job_label('job/../x')\n"
)


class DraftOnlyStub:
    swayz_draft_only = True

    def __init__(self):
        self.events = []

    def read_branch_head(self, repo, branch):
        assert repo == REPO and branch == "main"
        return BASE

    def branch_exists(self, repo, branch):
        return False

    def create_branch(self, repo, branch, sha):
        assert repo == REPO and sha == BASE
        self.events.append("branch")

    def put_new_file(self, repo, branch, path, content):
        assert repo == REPO and path == "tests/test_generated_label.py"
        assert content == GENERATED_TEST
        self.events.append("file")

    def create_pull_request(self, repo, **kwargs):
        assert repo == REPO and kwargs["draft"] is True
        self.events.append("draft")
        return {"draft": True, "number": 1}


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise PermissionError("This test may only run in GitHub CI")
    digest_ref = subprocess.check_output(
        ["docker", "image", "inspect", "python:3.12-slim",
         "--format", "{{index .RepoDigests 0}}"], text=True, timeout=10).strip()
    if not digest_ref.startswith("python@sha256:"):
        raise RuntimeError("Approved immutable CI image unavailable")
    image = digest_ref.removeprefix("python@")

    with tempfile.TemporaryDirectory(prefix="swayz-reviewed-ci-") as directory:
        root = Path(directory)
        root.chmod(0o755)
        staging, snapshots = root / "staging", root / "snapshots"
        staging.mkdir(mode=0o755)
        snapshots.mkdir(mode=0o755)
        queue_path = str(root / "queue.db")
        stop_path = str(root / "stop.db")
        with sqlite3.connect(queue_path) as db:
            db.execute("CREATE TABLE development_tasks(job_id TEXT PRIMARY KEY, day_utc TEXT, task TEXT, state TEXT)")
            db.execute("INSERT INTO development_tasks VALUES (?,?,?,?)",
                       (JOB, "2026-11-22", "Create validated Python job label test", "queued"))
        with sqlite3.connect(stop_path) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,0)")

        def running():
            with sqlite3.connect(f"file:{stop_path}?mode=ro", uri=True) as db:
                if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchone() != (0,):
                    raise PermissionError("CI emergency stop engaged")

        # Simulated GPT output with canonical, content-bound digest.
        proposed = {
            "base_sha": BASE,
            "branch": "agent/ci-reviewed-code",
            "changes": [{"path": "tests/test_generated_label.py", "content": GENERATED_TEST}],
        }
        canonical = json.dumps(proposed, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        proposal_hash = hashlib.sha256(canonical.encode("ascii")).hexdigest()
        plan = json.dumps({**proposed, "proposal_sha256": proposal_hash},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        # Simulated Claude review of the same proposal identity. Never imply a
        # live model call took place here.
        review = json.dumps({"proposal_sha256": proposal_hash,
                             "approved": True, "findings": []})

        def execute_verified(*, job_id, plan):
            def execute_container(*, job_id, snapshot, snapshot_root, expected_hashes):
                worker = plan_worker_lifecycle(job_id, image, workspace=snapshot)
                transport = build_guarded_transport(worker, server_control_db=stop_path)
                outcome = run_supervised_lifecycle(
                    worker, transport=transport, daemon_probe=transport.daemon_healthy)
                return {"state": outcome.state, "cleanup_verified": outcome.cleanup_verified}

            return run_generated_code_tests(
                job_id=job_id, plan=plan, staging_root=str(staging),
                snapshot_root=str(snapshots), require_running=running,
                trusted_execute=execute_container)

        github = DraftOnlyStub()
        result = complete_supervised_cycle(
            job_id=JOB, task_queue=DevelopmentTaskQueue(queue_path),
            require_running=running, approved_base_sha=BASE,
            approved_proposal_sha256=proposal_hash, base_branch="main",
            coding_response=plan, review_response=review,
            run_verified_tests=execute_verified, github=github)
        if result.state != "done" or github.events != ["branch", "file", "draft"]:
            raise RuntimeError("Reviewed development integration did not complete")
        if DevelopmentTaskQueue(queue_path).get(JOB)["state"] != "done":
            raise RuntimeError("Durable queue state not completed")
        with sqlite3.connect(stop_path) as db:
            db.execute("UPDATE agent_control SET stopped=1 WHERE id=1")
        print("SWAYZ_REVIEWED_GENERATED_CODE_DOCKER_PASSED")
        print("SWAYZ_DRAFT_ONLY_STUB_PASSED")
        print("SWAYZ_CI_EMERGENCY_STOP_ENGAGED")


if __name__ == "__main__":
    main()
