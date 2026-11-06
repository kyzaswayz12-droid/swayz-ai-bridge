"""Operator-only bounded offline execution window.

Not a network endpoint or unattended activation. The operator must be
authenticated outside this module and the job must already be admitted,
its protected snapshot and immutable metadata independently verified.
Signing occurs inside the supervised window because the signer checks stop. Always re-engage the stop in finally.
"""
import os
from .emergency_stop import EmergencyStop


def run_supervised_window(*, job_id, verify_operator, verify_prepared_job,
                          execute_once, stop_db):
    if os.geteuid() != 0:
        raise PermissionError("Root operator required")
    if stop_db != "/var/lib/swayzcontrol/state/stop.db":
        raise PermissionError("Unexpected stop control path")
    if not all(callable(x) for x in (
            verify_operator, verify_prepared_job, execute_once)):
        raise PermissionError("Trusted operator callbacks required")
    # Never release stop before admission and immutable snapshot are verified.
    # The signer itself requires stop to be released, so signing MUST occur
    # inside execute_once, after independent watchdog restoration is armed.
    if verify_operator(job_id=job_id) is not True:
        raise PermissionError("Independent operator authentication required")
    if verify_prepared_job(job_id=job_id) is not True:
        raise PermissionError("Admitted job and protected snapshot required")
    control = EmergencyStop(stop_db)
    try:
        if not control.is_stopped():
            raise PermissionError("Supervised window requires initially engaged stop")
        # This boolean is meaningful only after independently authenticated
        # root operator verification above. Never expose via an AI callback.
        control.enable(owner_authorised=True)
        try:
            outcome = execute_once(job_id=job_id)
        finally:
            control.stop()
        if not isinstance(outcome, dict) or outcome.get("state") != "passed" or outcome.get("cleanup_verified") is not True:
            return {"job_id":job_id,"state":"blocked","cleanup_verified":False}
        return {"job_id":job_id,"state":"passed","cleanup_verified":True}
    finally:
        # Reassert stop even if the first restoration raised. For hard kills,
        # the operator must arrange independent systemd watchdog restoration.
        try:
            control.stop()
        finally:
            control.close()
