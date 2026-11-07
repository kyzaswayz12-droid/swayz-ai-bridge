"""One-shot operator-only signing and systemd execution from protected metadata.

This is not an unattended worker. Never releases the stop, admits jobs,
makes paid calls, or retries an uncertain outcome. A distinct operator
must have already admitted the job and staged verified protected metadata.
"""
import argparse
import json
import os
from .protected_admission_loader import load_protected_job
from .privileged_signing_receiver import receive_authorised_signing_request
from .persistent_stop_guard import PersistentStopGuard
from .systemd_generated_job_adapter import run_prepared_generated_job

def execute_operator_signed_job(*, job_id, load_job=load_protected_job,
                                receive=receive_authorised_signing_request,
                                execute=run_prepared_generated_job):
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    trusted = load_job(job_id)
    if not isinstance(trusted, dict) or trusted.get("job_id") != job_id:
        raise PermissionError("Protected job identity mismatch")
    if (trusted.get("stop_db") != "/var/lib/swayzcontrol/state/stop.db"
            or trusted.get("signing_key_file") != "/etc/swayz/executor-signing.key"
            or trusted.get("request_directory") != "/var/lib/swayz-executor/requests"):
        raise PermissionError("Unexpected privileged runtime paths")
    guard = PersistentStopGuard(trusted["stop_db"])
    guard.require_running()
    identity = {k: trusted[k] for k in (
        "job_id", "commit_sha", "proposal_sha256", "manifest_sha256")}
    receipt = receive(identity=identity, load_trusted_job=lambda *, job_id:load_job(job_id),
                      require_running=guard.require_running)
    if receipt != {"state":"admitted", "job_id":job_id}:
        raise PermissionError("Signer did not confirm admission")
    guard.require_running()
    result = execute(
        job_id=job_id, snapshot=trusted["snapshot"],
        snapshot_root=trusted["snapshot_root"],
        expected_hashes=trusted["expected_hashes"],
        signing_key_path=trusted["signing_key_file"],
        require_running=guard.require_running)
    if (not isinstance(result, dict) or result.get("state") != "passed"
            or result.get("cleanup_verified") is not True):
        return {"job_id":job_id,"state":"blocked","cleanup_verified":False}
    guard.require_running()
    return {"job_id":job_id,"state":"passed","cleanup_verified":True}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--job",required=True)
    args=parser.parse_args(argv)
    result=execute_operator_signed_job(job_id=args.job)
    print(json.dumps(result,sort_keys=True))
    return 0 if result["state"]=="passed" else 1

if __name__=="__main__":
    raise SystemExit(main())
