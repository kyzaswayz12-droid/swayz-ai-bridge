"""Pure Bridge-side control integration.

The bridge invokes this only after Slack HTTP signature verification.
The caller must enforce channel/user allowlists and durable deduplication.
No control service is enabled by importing this module.
"""
from .control import handle_control_event
from .core import Ignore, Reply


def dispatch_bridge_control(payload, settings, store, now, *, remote_client=None, validated_action=None):
    if remote_client is None:
        return handle_control_event(payload, settings, store, now)
    action = validated_action if validated_action is not None else handle_control_event(payload, settings, store, now)
    if not isinstance(action, Reply):
        return action
    parts = payload["event"]["text"].strip().split()
    operation = parts[1].lower()
    job_id = parts[2] if operation == "job" else None
    if operation == "job":
        operation = "job_status"
    try:
        result = remote_client.request(operation, job_id=job_id)
        if operation == "stop":
            if result.get("action") != "stop" or result.get("stopped") is not True:
                raise ValueError("Stop unconfirmed")
            message = "Swayz control-service stop recorded; worker execution shutdown not yet verified."
        elif operation == "status":
            if result.get("action") != "status" or type(result.get("stopped")) is not bool:
                raise ValueError("Status unconfirmed")
            message = "Swayz control stop: ENGAGED (worker state unverified)" if result["stopped"] else "Swayz control stop: NOT ENGAGED (worker state unverified)"
        else:
            if result.get("action") != "job_status" or result.get("job_id") != job_id:
                raise ValueError("Job status unconfirmed")
            if result.get("state") not in ("not_found", "admitted", "running", "passed", "failed", "blocked"):
                raise ValueError("Invalid job state")
            message = "Job " + job_id + ": " + result["state"]
    except Exception:
        message = "Swayz control unavailable; action NOT confirmed."
    return Reply(action.channel, action.thread_ts, message)
