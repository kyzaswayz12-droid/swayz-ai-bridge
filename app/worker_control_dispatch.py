"""Pure Bridge-side control integration.

The bridge invokes this only after Slack HTTP signature verification.
The caller must enforce channel/user allowlists and durable deduplication.
No control service is enabled by importing this module.
"""
from .control import handle_control_event
from .core import Ignore, Reply


def dispatch_bridge_control(payload, settings, store, now, *, remote_client=None):
    if remote_client is None:
        return handle_control_event(payload, settings, store, now)
    raise RuntimeError("Remote routing not installed; worker control remains disabled")
