"""Offline Slack control-command parser for Swayz development.

The Slack Bridge MUST authenticate Slack request signatures, allowed channel,
and allowed user BEFORE calling this parser. No privileged action is taken.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SlackControlIntent:
    action: str
    job_id: str | None = None


_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def parse_slack_control(text):
    if not isinstance(text, str) or len(text) > 512:
        raise ValueError("Invalid Slack command")
    parts = text.strip().split()
    if not parts or parts[0].lower() != "swayz":
        raise ValueError("Not a Swayz control command")
    if len(parts) == 2 and parts[1].lower() in ("status", "stop"):
        return SlackControlIntent(parts[1].lower())
    if len(parts) == 3 and parts[1].lower() == "job" and _JOB.fullmatch(parts[2]):
        return SlackControlIntent("job_status", parts[2])
    raise ValueError("Unsupported Swayz command")
