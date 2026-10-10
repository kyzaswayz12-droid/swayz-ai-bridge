"""Sandbox-only subscriber publication smoke test.

No external HTTP calls; uses mock provider acknowledgement.
"""
import asyncio
from decimal import Decimal
from .publish import TradeUpdate, TradeMode, render_trade_update
from .outbox import PublicationOutbox
from .delivery import deliver_approved

class FakeResponse:
    def raise_for_status(self): return None
    def json(self): return {"ok": True, "result": {"message_id": 12345}}

class FakeTelegramClient:
    async def post(self, url, **kwargs):
        if not url.startswith("https://api.telegram.org/bot"):
            raise AssertionError("Unexpected endpoint")
        return FakeResponse()

async def run_sandbox_demo() -> dict:
    update=TradeUpdate("sandbox-001","BTC/USD","crypto","buy",
        Decimal("0.01"),Decimal("50000"),TradeMode.PAPER,"2026-10-10T12:00:00Z")
    text=render_trade_update(update,approved=True)
    outbox=PublicationOutbox()
    try:
        outbox.create_draft("telegram:sandbox-001","telegram",text)
        outbox.approve("telegram:sandbox-001","owner",{"owner"})
        receipt=await deliver_approved(outbox,"telegram:sandbox-001",FakeTelegramClient(),
            telegram_token="mock-token",telegram_chat_id="mock-chat")
        return {
            "mode": "sandbox",
            "publication_status": outbox.get("telegram:sandbox-001").status,
            "provider": receipt.provider,
            "external_id": receipt.external_id,
            "real_network_requests": 0,
        }
    finally:
        outbox.close()
