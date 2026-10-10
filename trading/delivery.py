"""Deliver approved paper-trade publications through injected HTTP client.

No broker connectivity, credentials, or automatic retries.
"""
from .outbox import PublicationOutbox
from .transports import send_telegram, send_discord, DeliveryReceipt

async def deliver_approved(
    outbox: PublicationOutbox,
    publication_id: str,
    client,
    *,
    telegram_token: str = "",
    telegram_chat_id: str = "",
    discord_webhook_url: str = "",
) -> DeliveryReceipt:
    item = outbox.get(publication_id)
    if item is None or item.status != "approved" or not item.approved_by:
        raise PermissionError("Publication is not approved")
    if not outbox.claim(publication_id):
        raise RuntimeError("Publication already claimed")
    try:
        if item.channel == "telegram":
            receipt = await send_telegram(client, bot_token=telegram_token,
                                          chat_id=telegram_chat_id, text=item.text)
        elif item.channel == "discord":
            receipt = await send_discord(client, webhook_url=discord_webhook_url,
                                         text=item.text)
        else:
            raise ValueError("Unsupported publication channel")
    except Exception:
        # Uncertain network outcomes require manual reconciliation.
        outbox.mark_failed(publication_id)
        raise
    if not outbox.mark_sent(publication_id, receipt.external_id):
        raise RuntimeError("Delivery acknowledged but receipt persistence failed")
    return receipt
