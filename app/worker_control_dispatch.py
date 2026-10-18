"""Pure Bridge-side control integration.

The bridge invokes this only after Slack HTTP signature verification.
The caller must enforce channel/user allowlists and durable deduplication.
No control service is enabled by importing this module.
"""
from .control import handle_control_event


def dispatch_bridge_control(payload, settings, store, now, *, remote_client=None):
    if remote_client is None:
        return handle_control_event(payload, settings, store, now)
    # Import from a deployed, explicitly packaged dev-agent integration.
    # Fail closed if not installed; never fall back to a false success.
    try:
        from agent.slack_remote_control import route_verified_remote_control
    except ImportError:
        raise RuntimeError("Remote worker control integration unavailable")
    result = route_verified_remote_control(
        payload, settings, store, now, client=remote_client)
    from .core import Ignore, Reply
    if result.__class__.__name__ == "Reply":
        return Reply(result.channel, result.thread_ts, result.text)
    return Ignore(result.reason)
