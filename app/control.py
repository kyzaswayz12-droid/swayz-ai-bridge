"""Bridge-side Swayz control routing, disabled unless explicitly enabled.

This layer only recognises requests and returns a truthful disconnected
status. Privileged stop/status forwarding requires a separately authenticated
worker control channel and is deliberately NOT implemented here.
"""
from dataclasses import dataclass
from .core import Ignore, Reply
import re

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def handle_control_event(payload, settings, store, now):
    if not isinstance(payload, dict) or payload.get("type") != "event_callback":
        return Ignore("not_control")
    event = payload.get("event")
    if not isinstance(event, dict) or event.get("type") != "message":
        return Ignore("not_control")
    if event.get("bot_id") or event.get("subtype"):
        return Ignore("bot_or_subtype")
    text = event.get("text")
    if not isinstance(text, str) or not text.strip().lower().startswith("swayz "):
        return Ignore("not_control")
    user, channel, ts = event.get("user"), event.get("channel"), event.get("ts")
    if not settings.allowed_channel or channel != settings.allowed_channel:
        return Ignore("channel_not_allowed")
    if not isinstance(user, str) or user not in settings.allowed_users:
        return Ignore("user_not_allowed")
    if not isinstance(ts, str) or not ts:
        return Ignore("missing_timestamp")
    parts = text.strip().split()
    if len(parts) == 2 and parts[1].lower() == "status":
        message = "Swayz worker control is not connected. No live worker status is available."
    elif len(parts) == 2 and parts[1].lower() == "stop":
        message = "Swayz stop was NOT executed: trusted worker control is not connected."
    elif len(parts) == 3 and parts[1].lower() == "job" and _JOB.fullmatch(parts[2]):
        message = "Swayz job lookup unavailable: trusted worker control is not connected."
    else:
        return Ignore("invalid_control")
    if not store.claim_message(channel, ts, now):
        return Ignore("duplicate")
    thread = event.get("thread_ts") if isinstance(event.get("thread_ts"), str) else None
    return Reply(channel, thread or ts, message)
