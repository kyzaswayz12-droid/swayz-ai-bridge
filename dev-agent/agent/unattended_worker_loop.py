"""Bounded unattended polling loop for the authorised Swayz development cycle.

This runner never signs jobs, opens the emergency stop, loads credentials,
or talks to Docker/GitHub directly. A separately authenticated service must
supply a fixed, authorised cycle (including paid GBP reservations, protected
signed execution, and draft-only GitHub). No automatic retry after failures.
"""
import time

def run_worker_loop(*, require_running, run_one_cycle, shutdown_requested,
                    sleep=time.sleep, poll_seconds=15, max_cycles=20, max_empty_polls=240):
    if not all(callable(x) for x in (require_running, run_one_cycle,
                                     shutdown_requested, sleep)):
        raise PermissionError("Trusted worker dependencies required")
    if type(poll_seconds) is not int or not 1 <= poll_seconds <= 300:
        raise ValueError("Invalid polling interval")
    if type(max_cycles) is not int or not 1 <= max_cycles <= 20:
        raise ValueError("Worker cycle cap must be within daily job limit")
    if type(max_empty_polls) is not int or not 1 <= max_empty_polls <= 240:
        raise ValueError("Invalid idle poll limit")
    processed = 0
    empty_polls = 0
    while processed < max_cycles:
        if shutdown_requested():
            return {"state": "stopped", "processed": processed}
        require_running()
        result = run_one_cycle()
        if not isinstance(result, dict) or result.get("state") not in (
                "empty", "done", "blocked"):
            raise PermissionError("Unexpected cycle result; worker halted")
        if result["state"] == "empty":
            empty_polls += 1
            if empty_polls >= max_empty_polls:
                return {"state": "idle_limit", "processed": processed}
            require_running()
            sleep(poll_seconds)
            continue
        empty_polls = 0
        processed += 1
        # Any blocked or uncertain job halts processing; never automatically
        # retry, move on to a different job, or release the emergency stop.
        if result["state"] == "blocked":
            return {"state": "blocked", "processed": processed}
        if not isinstance(result.get("draft_pr"), dict) or result["draft_pr"].get("draft") is not True:
            raise PermissionError("Completed cycle lacks verified draft PR")
        require_running()
    return {"state": "cycle_limit", "processed": processed}
