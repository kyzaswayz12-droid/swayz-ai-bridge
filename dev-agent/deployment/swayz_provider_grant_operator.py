"""Explicitly operator-controlled root grant issuance, DISABLED by default.

Install/provision separately after review. Does not invoke providers, Docker,
GitHub or trading, and never uses the existing Docker signing key.
"""
import argparse
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from agent.protected_admission_writer import require_engaged_stop
from agent.split_provider_authority import issue_split_grant
from agent.split_provider_transport import publish_split_grant

KEY = Path("/etc/swayz-collaboration/provider-grant-signing.key")
PUB = Path("/var/lib/swayz-provider-inbox/provider-grant-public.key")
ROOT_GRANTS = "/var/lib/swayz-provider-grants"
INBOX = "/var/lib/swayz-provider-inbox"
BUDGET = "/var/lib/swayz-executor/budget.sqlite3"
CONFIG = Path("/etc/swayz-collaboration")


def main(argv=None):
    parser=argparse.ArgumentParser(description="Explicit, one-shot Swayz provider grant operator")
    parser.add_argument("--job",required=True)
    parser.add_argument("--base-sha",required=True)
    parser.add_argument("--issue-and-publish",action="store_true")
    args=parser.parse_args(argv)
    if not args.issue_and_publish:
        parser.error("Disabled; explicit --issue-and-publish required")
    if os.geteuid()!=0:
        raise PermissionError("Root operator required")
    info=KEY.stat()
    if (KEY.is_symlink() or not KEY.is_file() or info.st_uid!=0
            or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size!=32):
        raise PermissionError("Dedicated provider key not provisioned safely")
    private=Ed25519PrivateKey.from_private_bytes(KEY.read_bytes())
    public=private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    trust=PUB.stat()
    if (PUB.is_symlink() or not PUB.is_file() or trust.st_uid!=0
            or stat.S_IMODE(trust.st_mode)!=0o640
            or PUB.read_bytes()!=public):
        raise PermissionError("Pinned root-owned public key not installed")
    require_engaged_stop()
    challenge="AUTHORISE PROVIDER GRANT "+args.job
    if input("Type "+challenge+": ")!=challenge:
        raise PermissionError("Independent operator confirmation required")
    issued=issue_split_grant(
        job_id=args.job,base_sha=args.base_sha,
        openai_card=CONFIG/"openai-rate.json",
        claude_card=CONFIG/"claude-rate.json",
        fx_card=CONFIG/"fx.json",gbp_budget_db=BUDGET,
        require_stop_engaged=require_engaged_stop,
        verify_owner=lambda job: job==args.job,
        signing_key=private,now=datetime.now(timezone.utc),
        output_directory=ROOT_GRANTS)
    published=publish_split_grant(
        source=issued["path"],inbox=INBOX,
        job_id=args.job,worker_group="swayzdev",
        require_stop_engaged=require_engaged_stop)
    print(json.dumps({"job_id":args.job,"state":published["state"],
                      "grant_sha256":published["grant_sha256"],
                      "provider_calls":0},sort_keys=True))


if __name__=="__main__":
    main()
