"""Offline root stop-proof socket tests: real UNIX sockets, no API requests."""
import hashlib
import json
import os
import socket
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent.split_provider_authority import issue_split_grant
from agent.provider_stop_proof_socket import _answer, serve_one_peer
from agent.split_provider_transport import _verify_stop_proof

NOW=datetime(2026,11,22,17,0,tzinfo=timezone.utc)
JOB="socket-proof-test-1"
BASE="a"*40


class RootStopProofTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root=Path(t.name)
        self.grants=root/"root_grants"
        self.grants.mkdir(mode=0o700)
        self.budget=root/"budget.sqlite3"
        self.stop=root/"stop.db"
        self.openai=root/"openai.json"
        self.claude=root/"claude.json"
        self.fx=root/"fx.json"
        with sqlite3.connect(self.budget) as db:
            db.execute("""CREATE TABLE gbp_reservations(request_id TEXT PRIMARY KEY,
                provider TEXT,day_utc TEXT,reserved_gbp TEXT,status TEXT,actual_gbp TEXT)""")
        with sqlite3.connect(self.stop) as db:
            db.execute("CREATE TABLE agent_control(id INTEGER PRIMARY KEY, stopped INTEGER)")
            db.execute("INSERT INTO agent_control VALUES(1,1)")
        common=dict(verified_on="2026-11-22",expires_on="2026-11-29",
                    verified_by_owner=True,source_url="https://example.com")
        self.openai.write_text(json.dumps({**common,"provider":"openai",
            "model":"gpt-5-mini","input_per_million_usd":"0.25",
            "output_per_million_usd":"2.00"}))
        self.claude.write_text(json.dumps({**common,"provider":"anthropic",
            "model":"claude-haiku-4-5-20251001","input_per_million_usd":"1.00",
            "output_per_million_usd":"5.00"}))
        self.fx.write_text(json.dumps({**common,"base":"USD","quote":"GBP",
            "gbp_per_usd":"0.80"}))
        self.signer=Ed25519PrivateKey.generate()
        def stopped():
            with sqlite3.connect(self.stop) as db:
                if db.execute("SELECT stopped FROM agent_control").fetchone()!=(1,):
                    raise PermissionError("Stopped")
        with patch("agent.split_provider_authority.os.geteuid",return_value=0):
            issue_split_grant(job_id=JOB,base_sha=BASE,openai_card=self.openai,
                claude_card=self.claude,fx_card=self.fx,gbp_budget_db=self.budget,
                require_stop_engaged=stopped,verify_owner=lambda job:job==JOB,
                signing_key=self.signer,now=NOW,output_directory=self.grants)
        self.grant=(self.grants/(JOB+".grant.json")).read_bytes()
        self.original_stat=Path.stat

    def root_directory_stat(self,path,*args,**kwargs):
        st=self.original_stat(path,*args,**kwargs)
        if path==self.grants:
            return SimpleNamespace(st_uid=0,st_mode=st.st_mode)
        return st

    def answer(self,**kwargs):
        request={"job_id":JOB,"phase":"openai",
                 "grant_sha256":hashlib.sha256(self.grant).hexdigest()}
        request.update(kwargs.pop("request",{}))
        with patch("agent.provider_stop_proof_socket.Path.stat",self.root_directory_stat), \
             patch("agent.split_provider_transport.os.geteuid",return_value=0):
            return _answer(request=request,peer_uid=os.getuid(),
                allowed_uid=os.getuid(),root_grants=self.grants,
                signing_key=self.signer,budget_db=self.budget,
                stop_db=self.stop,now=NOW,**kwargs)

    def test_signed_root_proof_bound_to_grant_and_phase(self):
        proof=self.answer()
        _verify_stop_proof(proof=proof,grant_bytes=self.grant,job_id=JOB,
            phase="openai",public_key=self.signer.public_key(),now=NOW)
        with self.assertRaises(PermissionError):
            _verify_stop_proof(proof=proof,grant_bytes=self.grant,job_id=JOB,
                phase="anthropic",public_key=self.signer.public_key(),now=NOW)

    def test_budget_reservation_required(self):
        with sqlite3.connect(self.budget) as db:
            db.execute("DELETE FROM gbp_reservations WHERE provider=?",("anthropic",))
        with self.assertRaises(PermissionError):
            self.answer()

    def test_stop_engaged_required(self):
        with sqlite3.connect(self.stop) as db:
            db.execute("UPDATE agent_control SET stopped=0")
        with self.assertRaises(PermissionError):
            self.answer()

    def test_wrong_peer_rejected(self):
        with self.assertRaises(PermissionError):
            self.answer(allowed_uid=os.getuid()+1)

    def test_tampered_grant_digest_rejected(self):
        with self.assertRaises(PermissionError):
            self.answer(request={"grant_sha256":"0"*64})

    def test_local_socket_peer_credential_is_checked(self):
        a,b=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM)
        a.settimeout(3)
        b.settimeout(3)
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        failures=[]
        def serve():
            try:
                with patch("agent.provider_stop_proof_socket.Path.stat",self.root_directory_stat), \
                     patch("agent.provider_stop_proof_socket.os.geteuid",return_value=0):
                    serve_one_peer(connection=a,allowed_uid=os.getuid(),
                        root_grants=self.grants,signing_key=self.signer,
                        budget_db=self.budget,stop_db=self.stop,now=NOW)
            except Exception as error:
                failures.append(error)
        thread=threading.Thread(target=serve)
        thread.start()
        self.addCleanup(lambda:thread.join(timeout=2))
        request={"job_id":JOB,"phase":"anthropic",
                 "grant_sha256":hashlib.sha256(self.grant).hexdigest()}
        b.sendall(json.dumps(request).encode()+b"\n")
        reply=b""
        while not reply.endswith(b"\n"):
            reply+=b.recv(4096)
        thread.join(timeout=2)
        self.assertFalse(failures, repr(failures))
        self.assertTrue(reply.endswith(b"\\n"))
        _verify_stop_proof(proof=reply[:-1],grant_bytes=self.grant,job_id=JOB,
            phase="anthropic",public_key=self.signer.public_key(),now=NOW)


if __name__=="__main__":
    unittest.main()
