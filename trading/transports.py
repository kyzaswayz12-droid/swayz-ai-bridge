"""Async delivery adapters. No credentials or network calls at import time.

Call only after durable outbox approval; do not retry uncertain outcomes.
"""
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class DeliveryReceipt:
    provider: str
    external_id: str

class DeliveryError(RuntimeError):
    pass

async def send_telegram(client: Any, *, bot_token: str, chat_id: str, text: str) -> DeliveryReceipt:
    if not bot_token or not chat_id or not text.startswith("PAPER TRADE — SIMULATED, NOT REAL MONEY"):
        raise ValueError("Invalid Telegram publication")
    response = await client.post(
        "https://api.telegram.org/bot" + bot_token + "/sendMessage",
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
        timeout=15)
    response.raise_for_status()
    body = response.json()
    if not body.get("ok") or not body.get("result", {}).get("message_id"):
        raise DeliveryError("Telegram did not acknowledge delivery")
    return DeliveryReceipt("telegram", str(body["result"]["message_id"]))

async def send_discord(client: Any, *, webhook_url: str, text: str) -> DeliveryReceipt:
    if not webhook_url.startswith("https://discord.com/api/webhooks/"):
        raise ValueError("Invalid Discord webhook URL")
    if not text.startswith("PAPER TRADE — SIMULATED, NOT REAL MONEY"):
        raise ValueError("Invalid Discord publication")
    response = await client.post(
        webhook_url, params={"wait": "true"},
        json={"content": text, "allowed_mentions": {"parse": []}}, timeout=15)
    response.raise_for_status()
    body = response.json()
    if not body.get("id"):
        raise DeliveryError("Discord did not acknowledge delivery")
    return DeliveryReceipt("discord", str(body["id"]))
