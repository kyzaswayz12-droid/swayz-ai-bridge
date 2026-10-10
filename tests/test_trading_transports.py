import asyncio
import pytest
from trading.transports import send_telegram, send_discord, DeliveryError

TEXT="PAPER TRADE — SIMULATED, NOT REAL MONEY\nPaper BTC/USD buy"

class Response:
    def __init__(self, payload):
        self.payload=payload
    def raise_for_status(self):
        pass
    def json(self):
        return self.payload

class Client:
    def __init__(self, payload):
        self.payload=payload
        self.calls=[]
    async def post(self, url, **kwargs):
        self.calls.append((url,kwargs))
        return Response(self.payload)

def test_telegram_delivery_receipt():
    c=Client({"ok":True,"result":{"message_id":123}})
    result=asyncio.run(send_telegram(c,bot_token="test-token",chat_id="-1001",text=TEXT))
    assert result.external_id=="123"
    assert c.calls[0][1]["json"]["disable_web_page_preview"]

def test_discord_mentions_disabled():
    c=Client({"id":"abc"})
    result=asyncio.run(send_discord(c,webhook_url="https://discord.com/api/webhooks/123/abc",text=TEXT))
    assert result.external_id=="abc"
    assert c.calls[0][1]["json"]["allowed_mentions"]=={"parse":[]}

def test_provider_nonacknowledgement():
    c=Client({"ok":False})
    with pytest.raises(DeliveryError):
        asyncio.run(send_telegram(c,bot_token="test",chat_id="1",text=TEXT))

def test_unapproved_format_rejected_without_network():
    c=Client({"id":"abc"})
    with pytest.raises(ValueError):
        asyncio.run(send_discord(c,webhook_url="https://discord.com/api/webhooks/123/abc",text="BUY NOW"))
    assert not c.calls
