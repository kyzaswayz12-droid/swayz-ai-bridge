"""Transport-neutral subscriber publishing with mandatory human approval.

This module never performs HTTP requests and never places trades.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Callable
from .publish import TradeUpdate, render_trade_update

class Channel(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"

@dataclass(frozen=True)
class Publication:
    publication_id: str
    channel: Channel
    text: str
    approved_by: str

class Publisher:
    def __init__(self, approved_users: set[str]):
        self.approved_users = frozenset(approved_users)
        self._published_ids: set[str] = set()

    def prepare(self, update: TradeUpdate, channel: Channel, approver: str) -> Publication:
        if not isinstance(channel, Channel):
            raise ValueError("Unsupported channel")
        if not approver or approver not in self.approved_users:
            raise PermissionError("Not an authorised publisher")
        text = render_trade_update(update, approved=True)
        return Publication(f"{channel.value}:{update.trade_id}", channel, text, approver)

    def dispatch(self, publication: Publication, send: Callable[[Channel, str], None]) -> None:
        """Explicit send callback. No retries or live network adapters are bundled."""
        if publication.approved_by not in self.approved_users:
            raise PermissionError("Publication approver no longer authorised")
        if not publication.text.startswith("PAPER TRADE — SIMULATED, NOT REAL MONEY"):
            raise ValueError("Publication must disclose simulation")
        if publication.publication_id in self._published_ids:
            raise ValueError("Already dispatched")
        # In-process only: a persistent outbox and provider idempotency are
        # required before production network delivery.
        send(publication.channel, publication.text)
        self._published_ids.add(publication.publication_id)
