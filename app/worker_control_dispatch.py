"""Pure Bridge-side control integration.

The bridge invokes this only after Slack HTTP signature verification.
The caller must enforce channel/user allowlists and durable deduplication.
No control service is enabled by importing this module.
"""
from .control import handle_control_event
from .core import Ignore, Reply
import hashlib
import logging

logger = logging.getLogger("swayz.bridge.control")


def dispatch_bridge_control(payload, settings, store, now, *, remote_client=None, validated_action=None):
    if remote_client is None:
        return handle_control_event(payload, settings, store, now)
    action = validated_action if validated_action is not None else handle_control_event(payload, settings, store, now)
    if not isinstance(action, Reply):
        return action
    parts = payload["event"]["text"].strip().split()
    operation = parts[1].lower()
    job_id = parts[2] if operation == "job" else None
    task = None
    if operation in ("develop", "stage"):
        task = payload["event"]["text"].strip().split(None, 2)[2].strip()
        event = payload["event"]
        job_id = "slack-" + hashlib.sha256((event["channel"] + ":" + event["ts"]).encode()).hexdigest()[:24]
    if operation == "job":
        operation = "job_status"
    try:
        if operation in ("develop", "stage"):
            result = remote_client.request(operation, job_id=job_id, task=task)
        else:
            result = remote_client.request(operation, job_id=job_id)
        if operation == "stop":
            if result.get("action") != "stop" or result.get("stopped") is not True:
                raise ValueError("Stop unconfirmed")
            message = "Swayz control-service stop recorded; worker execution shutdown not yet verified."
        elif operation == "status":
            if result.get("action") != "status" or type(result.get("stopped")) is not bool:
                raise ValueError("Status unconfirmed")
            message = "Swayz control stop: ENGAGED (worker state unverified)" if result["stopped"] else "Swayz control stop: NOT ENGAGED (worker state unverified)"
        elif operation == "stage":
            if result.get("action") != "stage" or result.get("job_id") != job_id or result.get("state") != "held":
                raise ValueError("Held staging unconfirmed")
            message = "Development task held: " + job_id + " (not executable; emergency stop unchanged)."
        elif operation == "develop":
            if result.get("action") != "develop" or result.get("job_id") != job_id or result.get("state") != "queued":
                raise ValueError("Development admission unconfirmed")
            message = "Development task queued: " + job_id + " (execution disabled until authorised)."
        else:
            if result.get("action") != "job_status" or result.get("job_id") != job_id:
                raise ValueError("Job status unconfirmed")
            if result.get("state") not in ("not_found", "queued", "claimed", "done", "admitted", "running", "passed", "failed", "blocked"):
                raise ValueError("Invalid job state")
            message = "Job " + job_id + ": " + result["state"]
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        logger.exception("remote control failed operation=%s job_id=%s error=%s status=%s",
                         operation, job_id, type(exc).__name__, status)
        message = "Swayz control unavailable; action NOT confirmed."
    return Reply(action.channel, action.thread_ts, message)
