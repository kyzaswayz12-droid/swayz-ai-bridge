"""Explicit swayzdev-only paid proposal worker. No automatic invocation.

Requires separately provisioned dedicated provider key, root proof socket,
root-issued/verified GBP grant and protected worker-only directories.
NEVER runs Docker or writes GitHub. Operator must explicitly approve paid use.
"""
import argparse
import grp
import json
import os
import pwd
import stat
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from agent.split_provider_transport import run_signed_provider_handoff
from agent.provider_stop_proof_socket import request_stop_proof_socket

INBOX = Path("/var/lib/swayz-provider-inbox")
PUB = INBOX / "provider-grant-public.key"
SOCKET = Path("/run/swayz-provider-proofs/stop-proof.sock")
CREDS = "/home/swayzdev/swayz-agent/secrets/providers.env"
CLAIMS = "/home/swayzdev/swayz-agent/data/provider-claims"
RESULTS = "/home/swayzdev/swayz-agent/data/provider-results"


def main(argv=None):
    parser=argparse.ArgumentParser(description="One authorised GPT-Claude proposal-only request")
    parser.add_argument("--job",required=True)
    parser.add_argument("--base-sha",required=True)
    parser.add_argument("--execute-paid",action="store_true")
    args=parser.parse_args(argv)
    if not args.execute_paid:
        parser.error("No paid calls without --execute-paid")
    uid=pwd.getpwnam("swayzdev").pw_uid
    gid=grp.getgrnam("swayzdev").gr_gid
    if os.geteuid()!=uid:
        raise PermissionError("Must run as swayzdev, never root")
    parent=INBOX.stat()
    info=PUB.stat()
    if (INBOX.is_symlink() or parent.st_uid!=0 or parent.st_gid!=gid
            or stat.S_IMODE(parent.st_mode)!=0o750
            or PUB.is_symlink() or not PUB.is_file()
            or info.st_uid!=0 or info.st_gid!=gid
            or stat.S_IMODE(info.st_mode)!=0o640 or info.st_size!=32):
        raise PermissionError("Root-pinned provider grant public key missing")
    key=Ed25519PublicKey.from_public_bytes(PUB.read_bytes())
    challenge="AUTHORISE PAID GPT CLAUDE "+args.job
    if input("Type "+challenge+": ")!=challenge:
        raise PermissionError("Operator paid-call confirmation required")
    result=run_signed_provider_handoff(
        job_id=args.job,base_sha=args.base_sha,inbox=INBOX,public_key=key,
        credential_file=CREDS,claimed_directory=CLAIMS,
        checkpoint_dir=RESULTS,
        get_fresh_stop_proof=lambda phase,grant: request_stop_proof_socket(
            socket_path=SOCKET,phase=phase,grant_bytes=grant,job_id=args.job))
    # Never print raw model responses or provider secrets to the terminal.
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
