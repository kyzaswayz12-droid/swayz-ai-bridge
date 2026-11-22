"""One isolated REAL-UID root -> swayzdev offline integration test.

Never touches real credentials, production budget, production provider grants,
production signing keys, Docker, GitHub writes or provider APIs. Generates an
ephemeral signer, fake credential file, fake GBP ledger, fake engaged STOP DB,
and Unix proof socket beneath a temporary root directory. All test artefacts
are removed afterwards. A production STOP check is read-only.

Requires explicit --offline-test; no paid-call option is implemented.
"""
import argparse
import grp
import hashlib
import json
import os
import pwd
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from agent.split_provider_authority import issue_split_grant, TASK
from agent.split_provider_transport import publish_split_grant
from agent.provider_stop_proof_socket import serve_one_peer

JOB = "offline-real-uid-handoff"
BASE = "a" * 40
PRODUCTION_STOP = Path("/var/lib/swayzcontrol/state/stop.db")
PRODUCTION_EXECUTOR = Path("/opt/swayz/executor-app")
PRODUCTION_BUDGET = Path("/var/lib/swayz-executor/budget.sqlite3")

# Runs as swayzdev, in a separate subprocess with the installed module.
# Uses synthetic credentials and an injected fake transport only.
WORKER = r'''
import json
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from agent.split_provider_transport import run_signed_provider_handoff
from agent.provider_stop_proof_socket import request_stop_proof_socket

root = Path(sys.argv[1])
job = sys.argv[2]
base = sys.argv[3]
public = Ed25519PublicKey.from_public_bytes((root / "inbox/public.key").read_bytes())
calls = []
def offline_transport(provider, payload, key):
    calls.append(provider)
    if provider == "openai":
        assert key == "synthetic-openai"
        assert payload["store"] is False
        proposal = {"base_sha": base, "branch": "agent/offline-signed-test",
                    "changes": [{"path": "tests/test_job_label.py",
                                 "content": "import unittest\nclass Labels(unittest.TestCase):\n def test_valid(self): self.assertTrue(True)\n"}],
                    "proposal_sha256": "0" * 64}
        response = {"output":[{"content":[{"type":"output_text","text":json.dumps(proposal)}]}],
                    "usage":{"input_tokens":100, "output_tokens":80}}
        return json.dumps(response).encode()
    assert provider == "anthropic"
    assert key == "synthetic-anthropic"
    digest = json.loads(payload["messages"][0]["content"])["proposal_sha256"]
    response = {"stop_reason":"end_turn",
                "content":[{"type":"text","text":json.dumps({
                    "proposal_sha256":digest, "approved":True, "findings":[]})}],
                "usage":{"input_tokens":100, "output_tokens":30}}
    return json.dumps(response).encode()

def run():
    return run_signed_provider_handoff(
        job_id=job, base_sha=base, inbox=root / "inbox",
        public_key=public, credential_file=root / "worker/credentials.env",
        claimed_directory=root / "worker/claims",
        checkpoint_dir=root / "worker/results",
        get_fresh_stop_proof=lambda phase, grant: request_stop_proof_socket(
            socket_path=root / "proof.sock", phase=phase,
            grant_bytes=grant, job_id=job),
        transport=offline_transport, simulated=True)

first = run()
assert first["state"] == "operator_review_required"
assert first["provider_calls"] == 0
assert calls == ["openai", "anthropic"]
result = json.loads((root / "worker/results" / (job + ".result.json")).read_text())
assert result["simulated"] is True and result["execution_authorised"] is False
assert result["github_writes"] == 0 and result["docker_executed"] is False
try:
    run()
except FileExistsError:
    pass
else:
    raise AssertionError("Replay was accepted")
assert calls == ["openai", "anthropic"], "Replay initiated a provider attempt"
print("REAL_UID_ONE_SHOT_PASS")
print("REPLAY_DENIED")
'''


def _real_stop_engaged():
    p = PRODUCTION_STOP
    if p.is_symlink() or not p.is_file():
        raise PermissionError("Production emergency-stop database unavailable")
    with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchall() != [(1,)]:
            raise PermissionError("Production emergency stop must remain engaged")


def _fake_stop_engaged(path):
    with sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchall() != [(1,)]:
            raise PermissionError("Simulated emergency stop must remain engaged")


def _directory(path, mode, uid, gid):
    path.mkdir(mode=mode)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def _write(path, data, mode=0o600, uid=0, gid=0):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode)
    with os.fdopen(fd, "wb") as out:
        os.fchown(out.fileno(), uid, gid)
        os.fchmod(out.fileno(), mode)
        out.write(data)


def _run():
    if os.geteuid() != 0:
        raise PermissionError("This offline cross-account test requires root")
    if not PRODUCTION_EXECUTOR.is_dir() or not PRODUCTION_BUDGET.is_file():
        raise PermissionError("Expected working executor/budget paths missing")
    _real_stop_engaged()
    swayz = pwd.getpwnam("swayzdev")
    gid = grp.getgrnam("swayzdev").gr_gid

    with tempfile.TemporaryDirectory(prefix="swayz-offline-uid-") as tmp:
        root = Path(tmp)
        os.chmod(root, 0o755)  # Traversal only; child secrets remain protected.
        _directory(root / "grants", 0o700, 0, 0)
        _directory(root / "inbox", 0o750, 0, gid)
        _directory(root / "worker", 0o700, swayz.pw_uid, gid)
        _directory(root / "worker/claims", 0o700, swayz.pw_uid, gid)
        _directory(root / "worker/results", 0o700, swayz.pw_uid, gid)
        _write(root / "worker/credentials.env",
               b"OPENAI_API_KEY=synthetic-openai\nANTHROPIC_API_KEY=synthetic-anthropic\n",
               uid=swayz.pw_uid, gid=gid)

        now = datetime.now(timezone.utc)
        expires = (now.date()).isoformat()
        common = dict(verified_by_owner=True, verified_on=expires,
                      expires_on=expires, source_url="https://example.com/offline-test")
        for name, data in (
            ("openai.json", dict(**common, provider="openai", model="gpt-5-mini",
                                 input_per_million_usd="0.25", output_per_million_usd="2.00")),
            ("claude.json", dict(**common, provider="anthropic",
                                 model="claude-haiku-4-5-20251001",
                                 input_per_million_usd="1.00", output_per_million_usd="5.00")),
            ("fx.json", dict(**common, base="USD", quote="GBP", gbp_per_usd="0.80")),
        ):
            _write(root / name, json.dumps(data).encode())

        fake_budget = root / "fake-budget.sqlite3"
        fake_stop = root / "fake-stop.sqlite3"
        with sqlite3.connect(fake_budget) as db:
            db.execute("""CREATE TABLE gbp_reservations (
                request_id TEXT PRIMARY KEY, provider TEXT NOT NULL,
                day_utc TEXT NOT NULL, reserved_gbp TEXT NOT NULL,
                status TEXT NOT NULL, actual_gbp TEXT)""")
        with sqlite3.connect(fake_stop) as db:
            db.execute("CREATE TABLE agent_control (id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES (1,1)")
        signer = Ed25519PrivateKey.generate()  # In memory, ephemeral, never production key.
        pub = signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        _write(root / "inbox/public.key", pub, 0o640, 0, gid)

        issued = issue_split_grant(
            job_id=JOB, base_sha=BASE, openai_card=root / "openai.json",
            claude_card=root / "claude.json", fx_card=root / "fx.json",
            gbp_budget_db=str(fake_budget),
            require_stop_engaged=lambda: _fake_stop_engaged(fake_stop),
            verify_owner=lambda job: job == JOB, signing_key=signer,
            now=now, output_directory=str(root / "grants"))
        published = publish_split_grant(
            source=issued["path"], inbox=str(root / "inbox"),
            job_id=JOB, worker_group="swayzdev",
            require_stop_engaged=lambda: _fake_stop_engaged(fake_stop))
        if published["provider_calls"] != 0:
            raise AssertionError("Unexpected provider call")

        with sqlite3.connect(fake_budget) as db:
            rows = db.execute(
                "SELECT provider,status FROM gbp_reservations ORDER BY provider").fetchall()
        if rows != [("anthropic", "reserved"), ("openai", "reserved")]:
            raise AssertionError("Expected two isolated reservations")

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.settimeout(0.25)
        server.bind(str(root / "proof.sock"))
        os.chown(root / "proof.sock", 0, gid)
        os.chmod(root / "proof.sock", 0o660)
        server.listen(5)
        done = threading.Event()
        failures = []

        def proof_loop():
            while not done.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError as exc:
                    if not done.is_set():
                        failures.append(type(exc).__name__)
                    break
                with conn:
                    try:
                        serve_one_peer(
                            connection=conn, allowed_uid=swayz.pw_uid,
                            root_grants=str(root / "grants"), signing_key=signer,
                            budget_db=str(fake_budget), stop_db=str(fake_stop))
                    except Exception as exc:
                        failures.append(type(exc).__name__)
        thread = threading.Thread(target=proof_loop, daemon=True)
        thread.start()
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            proc = subprocess.run(
                ["runuser", "-u", "swayzdev", "--", "env",
                 "PYTHONPATH=" + env["PYTHONPATH"], "PYTHONDONTWRITEBYTECODE=1",
                 "python3", "-B", "-c", WORKER, str(root), JOB, BASE],
                text=True, capture_output=True, timeout=30)
            if proc.returncode:
                raise RuntimeError(
                    "Offline swayzdev worker failed: " + proc.stderr[-1200:])
            if "REAL_UID_ONE_SHOT_PASS" not in proc.stdout or "REPLAY_DENIED" not in proc.stdout:
                raise RuntimeError("Offline worker returned incomplete success proof")
            if failures:
                raise RuntimeError("Root stop-proof service rejected a test request: " +
                                   ",".join(failures))
            _fake_stop_engaged(fake_stop)
            _real_stop_engaged()
            print("TEMPORARY_BUDGET_ONLY: PASS")
            print("ROOT_TO_SWAYZDEV_SIGNATURE_AND_SOCKET: PASS")
            print("REAL_UID_ONE_SHOT_PASS")
            print("REPLAY_DENIED")
            print("PRODUCTION_STOP_ENGAGED: PASS")
            print("PAID_PROVIDER_CALLS: 0")
        finally:
            done.set()
            server.close()
            thread.join(timeout=2)

    print("ISOLATED_TEST_FILES_CLEANED")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline real-UID signed handoff test")
    parser.add_argument("--offline-test", action="store_true")
    args = parser.parse_args(argv)
    if not args.offline_test:
        parser.error("Disabled by default: explicit --offline-test required")
    _run()


if __name__ == "__main__":
    main()
