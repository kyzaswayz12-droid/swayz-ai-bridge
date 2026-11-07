"""Operator-invoked root-only signer service entrypoint (not an unattended daemon).

A fixed root-owned metadata directory supplies the admission and paths.
The worker may submit only an identity, never key material or file paths.
This does not release the emergency stop or start Docker.
"""
import argparse
import json
import os
from .protected_admission_loader import load_protected_job
from .privileged_signing_receiver import receive_authorised_signing_request
from .persistent_stop_guard import PersistentStopGuard

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--job",required=True)
    parser.add_argument("--metadata-dir",
                        default="/var/lib/swayz-executor/admission-metadata")
    args=parser.parse_args(argv)
    if os.geteuid()!=0:
        raise PermissionError("Privileged signing service required")
    trusted=load_protected_job(args.job,metadata_directory=args.metadata_dir)
    identity={k:trusted[k] for k in (
        "job_id","commit_sha","proposal_sha256","manifest_sha256")}
    guard=PersistentStopGuard(trusted["stop_db"])
    result=receive_authorised_signing_request(
        identity=identity,
        load_trusted_job=lambda *,job_id:load_protected_job(
            job_id,metadata_directory=args.metadata_dir),
        require_running=guard.require_running)
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
