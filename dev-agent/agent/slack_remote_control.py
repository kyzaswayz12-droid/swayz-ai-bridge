"""Bridge-side adapter for verified Slack control messages.

Caller MUST verify Slack request signature, user/channel allowlist and
deduplication before invoking this adapter. No job submission or enable path.
"""
from .slack_verified_controls import Ignore, Reply
from .slack_control_intents import parse_slack_control


def route_verified_remote_control(payload, settings, store, now, *, client):
    if not isinstance(payload, dict) or payload.get("type") != "event_callback":
        return Ignore("invalid_payload")
    event = payload.get("event")
    if not isinstance(event, dict) or event.get("type") != "message":
        return Ignore("not_message")
    if event.get("bot_id") or event.get("subtype"):
        return Ignore("bot_message")
    user, channel, ts = event.get("user"), event.get("channel"), event.get("ts")
    if not isinstance(user, str) or user not in settings.allowed_users:
        return Ignore("unauthorised_user")
    if not settings.allowed_channel or channel != settings.allowed_channel:
        return Ignore("unauthorised_channel")
    if not isinstance(ts, str) or not ts:
        return Ignore("invalid_timestamp")
    text = event.get("text")
    if not isinstance(text, str) or not text.strip().lower().startswith("swayz "):
        return Ignore("not_control")
    try:
        intent = parse_slack_control(text)
    except ValueError:
        return Ignore("invalid_control")
    if intent.action not in {"status", "stop", "job_status"}:
        return Ignore("unsupported_control")
    if not store.claim_message(channel, ts, now):
        return Ignore("duplicate")
    thread = event.get("thread_ts") or ts
    try:
        result = client.request(intent.action, job_id=intent.job_id if intent.action == "job_status" else None)
        if intent.action == "stop":
            if result.get("stopped") is not True:
                raise ValueError("Stop not confirmed")
            message = "Swayz worker emergency stop confirmed."
        elif intent.action == "status":
            if type(result.get("stopped")) is not bool:
                raise ValueError("Invalid worker status")
            message = "Swayz worker: STOPPED" if result["stopped"] else "Swayz worker: ENABLED (execution health unverified)"
        else:
            if result.get("job_id") != intent.job_id or not isinstance(result.get("state"), str):
                raise ValueError("Invalid job response")
            message = f"Job {intent.job_id}: {result['state']}"
    except Exception:
        message = "Swayz worker control unavailable; action NOT confirmed. Check worker directly."
    return Reply(channel, thread, message)
