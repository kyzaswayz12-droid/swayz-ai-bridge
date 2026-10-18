"""Offline, authenticated Slack control routing for the existing Bridge.

Call ONLY after Slack's HTTP signature has been verified. Uses the Bridge's
channel/user allowlist and message deduplication. No Docker or paid APIs.
"""
from dataclasses import dataclass
from app.core import Ignore, Reply
from .slack_control_intents import parse_slack_control


def handle_verified_control_event(payload, settings, store, now, *,
                                  emergency_stop, journal):
    if not isinstance(payload, dict) or payload.get("type") != "event_callback":
        return Ignore("invalid_payload")
    event = payload.get("event")
    if not isinstance(event, dict) or event.get("type") != "message":
        return Ignore("not_message")
    if event.get("bot_id") or event.get("subtype"):
        return Ignore("bot_message")
    user, channel, ts = event.get("user"), event.get("channel"), event.get("ts")
    if not isinstance(user, str) or not user or user not in settings.allowed_users:
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
    if not store.claim_message(channel, ts, now):
        return Ignore("duplicate")
    thread = event.get("thread_ts") or ts
    if intent.action == "stop":
        emergency_stop.stop()
        message = "Swayz emergency stop engaged. New jobs must remain disabled."
    elif intent.action == "status":
        message = ("Swayz development dispatch: STOPPED" if emergency_stop.is_stopped()
                   else "Swayz development dispatch: ENABLED (worker health not verified)")
    elif intent.action == "job_status":
        record = journal.status(intent.job_id)
        message = (f"Job {intent.job_id}: {record[0]}" if record
                   else f"Job {intent.job_id}: not found")
    else:
        raise PermissionError("Unsupported control intent")
    return Reply(channel, thread, message)
