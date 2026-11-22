"""Mock-only split root->swayzdev proof and transport tests; zero real requests."""
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent.split_provider_authority import issue_split_grant
from agent.split_provider_transport import (
    publish_split_grant, issue_stop_proof, run_signed_provider_handoff,
)

NOW = datetime(2026, 11, 22, 17, 0, tzinfo=timezone.utc)
JOB = "provider-handoff-ci-1"
BASE = "a" * 40


class SplitProviderTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.root = root
        self.grants = root/"root_grants"
        self.inbox = root/"inbox"
        self.claims = root/"claims"
        self.results = root/"results"
        self.grants.mkdir(mode=0o700)
        self.inbox.mkdir(mode=0o750)
        self.claims.mkdir(mode=0o700)
        self.results.mkdir(mode=0o700)
        self.budget = root/"budget.sqlite3"
        self.stop = root/"stop.db"
        with sqlite3.connect(self.budget) as db:
            db.execute("""CREATE TABLE gbp_reservations(request_id TEXT PRIMARY KEY,
              provider TEXT,day_utc TEXT,reserved_gbp TEXT,
              status TEXT,actual_gbp TEXT)""")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY,stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,1)")
        self.creds = root/"providers.env"
        self.creds.write_text(chr(10).join([
            "OPENAI_API_KEY=dummy-openai", "ANTHROPIC_API_KEY=dummy-claude", ""]))
        self.creds.chmod(0o600)
        self.openai = root/"openai.json"
        self.claude = root/"claude.json"
        self.fx = root/"fx.json"
        common = dict(verified_on="2026-11-22",expires_on="2026-11-29",
                      verified_by_owner=True,source_url="https://example.com")
        self.openai.write_text(json.dumps(dict(**common,provider="openai",
            model="gpt-5-mini",input_per_million_usd="0.25",
            output_per_million_usd="2.00")))
        self.claude.write_text(json.dumps(dict(**common,provider="anthropic",
            model="claude-haiku-4-5-20251001",input_per_million_usd="1.00",
            output_per_million_usd="5.00")))
        self.fx.write_text(json.dumps(dict(**common,base="USD",quote="GBP",
                                          gbp_per_usd="0.80")))
        self.signer = Ed25519PrivateKey.generate()
        self.calls = []
        self.proofs = []
        self.grant_bytes = None

    def stop_check(self):
        with sqlite3.connect(self.stop) as db:
            if db.execute("SELECT stopped FROM agent_control WHERE id=1").fetchone() != (1,):
                raise PermissionError("STOP engaged required")

    def prepare(self):
        with patch("agent.split_provider_authority.os.geteuid",return_value=0):
            issue_split_grant(job_id=JOB,base_sha=BASE,openai_card=self.openai,
                 claude_card=self.claude,fx_card=self.fx,gbp_budget_db=self.budget,
                 require_stop_engaged=self.stop_check,
                 verify_owner=lambda job:job==JOB,
                 signing_key=self.signer,now=NOW,output_directory=self.grants)
        self.grant_bytes=(self.grants/(JOB+".grant.json")).read_bytes()
        (self.inbox/(JOB+".grant.json")).write_bytes(self.grant_bytes)

    def stop_proof(self,phase,grant_bytes):
        with patch("agent.split_provider_transport.os.geteuid",return_value=0):
            proof=issue_stop_proof(job_id=JOB,phase=phase,grant_bytes=grant_bytes,
                                  stop_db=self.stop,signing_key=self.signer,now=NOW)
        self.proofs.append(phase)
        return proof

    def fake_transport(self,provider,payload,key):
        self.calls.append(provider)
        if provider=="openai":
            self.assertEqual(key,"dummy-openai")
            self.assertEqual(payload["store"],False)
            code = {"base_sha": BASE, "branch": "agent/mock-provider-test",
                    "changes": [{
                        "path":"tests/test_job_label.py",
                        "content":"import unittest\nclass Labels(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n"
                    }], "proposal_sha256":"0"*64}
            result={"output":[{"content":[{"type":"output_text",
                                           "text":json.dumps(code)}]}],
                    "usage":{"input_tokens":100,"output_tokens":80}}
            return json.dumps(result).encode()
        self.assertEqual(key,"dummy-claude")
        digest=json.loads(payload["messages"][0]["content"])["proposal_sha256"]
        result={"stop_reason":"end_turn",
                "content":[{"type":"text","text":json.dumps(
                  {"proposal_sha256":digest,"approved":True,"findings":[]})}],
                "usage":{"input_tokens":100,"output_tokens":25}}
        return json.dumps(result).encode()

    def worker(self,**extra):
        args=dict(job_id=JOB,base_sha=BASE,inbox=self.inbox,
                  public_key=self.signer.public_key(),credential_file=self.creds,
                  claimed_directory=self.claims,checkpoint_dir=self.results,
                  get_fresh_stop_proof=self.stop_proof,
                  transport=self.fake_transport,simulated=True,now=NOW)
        args.update(extra)
        return run_signed_provider_handoff(**args)

    def test_complete_mocked_one_shot_and_no_replay(self):
        self.prepare()
        result=self.worker()
        self.assertEqual(result["state"],"operator_review_required")
        self.assertEqual(result["provider_calls"],0)
        self.assertEqual(self.calls,["openai","anthropic"])
        self.assertIn("anthropic",self.proofs)
        for name in ("openai-attempt","claude-attempt","openai.json","claude.json","result.json"):
            self.assertTrue((self.results/(JOB+"."+name)).is_file())
        self.assertTrue((self.claims/(JOB+".claimed")).is_file())
        with self.assertRaises(FileExistsError):
            self.worker()
        self.assertEqual(self.calls,["openai","anthropic"])
        self.stop_check()

    def test_invalid_signature_cannot_claim_or_call(self):
        self.prepare()
        with patch.object(self.signer,"public_key",return_value=Ed25519PrivateKey.generate().public_key()):
            with self.assertRaises(PermissionError):
                self.worker()
        self.assertEqual(self.calls,[])

    def test_stop_change_blocks_before_any_call(self):
        self.prepare()
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=0")
        with self.assertRaises(PermissionError):
            self.worker()
        self.assertEqual(self.calls,[])

    def test_stop_change_between_calls_blocks_claude(self):
        self.prepare()
        def stop_after_openai(provider,payload,key):
            raw=self.fake_transport(provider,payload,key)
            if provider=="openai":
                with sqlite3.connect(self.stop) as db:
                    db.execute("UPDATE agent_control SET stopped=0")
            return raw
        with self.assertRaises(PermissionError):
            self.worker(transport=stop_after_openai)
        self.assertEqual(self.calls,["openai"])
        self.assertFalse((self.results/(JOB+".claude-attempt")).exists())

    def test_transport_exception_no_retry(self):
        self.prepare()
        def fail(*args):
            self.calls.append(args[0])
            raise RuntimeError("unknown provider result")
        with self.assertRaises(RuntimeError):
            self.worker(transport=fail)
        self.assertEqual(self.calls,["openai"])
        with self.assertRaises(FileExistsError):
            self.worker(transport=fail)
        self.assertEqual(self.calls,["openai"])

    def test_live_transport_cannot_be_used_in_simulation(self):
        self.prepare()
        from agent.http_transport import provider_transport
        with self.assertRaises(PermissionError):
            self.worker(transport=provider_transport)
        self.assertEqual(self.calls,[])

    def test_custom_transport_cannot_be_used_in_live_mode(self):
        self.prepare()
        with self.assertRaises(PermissionError):
            self.worker(simulated=False)
        self.assertEqual(self.calls,[])

    def test_wrong_base_denied(self):
        self.prepare()
        with self.assertRaises(PermissionError):
            self.worker(base_sha="b"*40)
        self.assertEqual(self.calls,[])

    def test_expired_stop_proof_fails(self):
        self.prepare()
        from agent.split_provider_transport import issue_stop_proof
        def bad_proof(phase,grant_bytes):
            with patch("agent.split_provider_transport.os.geteuid",return_value=0):
                return issue_stop_proof(job_id=JOB,phase=phase,
                    grant_bytes=grant_bytes,stop_db=self.stop,
                    signing_key=self.signer,now=NOW.replace(minute=0))
        with self.assertRaises(PermissionError):
            self.worker(get_fresh_stop_proof=bad_proof,now=NOW.replace(minute=2))
        self.assertEqual(self.calls,[])

    def test_grant_transfer_has_no_side_effects(self):
        self.prepare()
        # Mock only directory ownership, never skip its restrictive mode.
        actual_stat=self.inbox.stat()
        from unittest.mock import patch as mock_patch
        class FakeStat:
            st_uid=0
            st_gid=os.getgid()
            st_mode=actual_stat.st_mode
        original_stat=Path.stat
        def stat(path,*args,**kwargs):
            if path == self.inbox:
                return FakeStat()
            return original_stat(path,*args,**kwargs)
        src=self.grants/(JOB+".grant.json")
        import grp
        with mock_patch("agent.split_provider_transport.os.geteuid",return_value=0), \
             mock_patch("agent.split_provider_transport.grp.getgrnam",
                        return_value=SimpleNamespace(gr_gid=os.getgid())), \
             mock_patch.object(Path,"stat",stat):
            output=publish_split_grant(
                source=src,inbox=self.inbox,job_id=JOB,worker_group="swayzdev",
                require_stop_engaged=self.stop_check) if not (self.inbox/(JOB+".grant.json")).exists() else None
        # Existing inbox file from setup is not overwritten.
        self.assertEqual((self.inbox/(JOB+".grant.json")).read_bytes(),self.grant_bytes)


if __name__=="__main__":
    unittest.main()
