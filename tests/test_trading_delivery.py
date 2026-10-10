import asyncio
import pytest
from trading.outbox import PublicationOutbox
from trading.delivery import deliver_approved

TEXT="PAPER TRADE — SIMULATED, NOT REAL MONEY\nBTC/USD test"

class Response:
    def __init__(self,payload): self.payload=payload
    def raise_for_status(self): pass
    def json(self): return self.payload

class Client:
    def __init__(self,payload): self.payload=payload; self.calls=0
    async def post(self,*args,**kwargs):
        self.calls+=1
        return Response(self.payload)

def make(channel):
    outbox=PublicationOutbox()
    outbox.create_draft("p1",channel,TEXT)
    return outbox

def test_telegram_end_to_end():
    o=make("telegram")
    c=Client({"ok":True,"result":{"message_id":42}})
    with pytest.raises(PermissionError):
        asyncio.run(deliver_approved(o,"p1",c,telegram_token="test",telegram_chat_id="1"))
    assert c.calls==0
    assert o.approve("p1","owner",{"owner"})
    receipt=asyncio.run(deliver_approved(o,"p1",c,telegram_token="test",telegram_chat_id="1"))
    assert receipt.external_id=="42"
    assert o.get("p1").status=="sent"
    with pytest.raises(PermissionError):
        asyncio.run(deliver_approved(o,"p1",c,telegram_token="test",telegram_chat_id="1"))
    assert c.calls==1

def test_discord_failed_ack_requires_manual_reconciliation():
    o=make("discord")
    assert o.approve("p1","owner",{"owner"})
    c=Client({})
    with pytest.raises(Exception):
        asyncio.run(deliver_approved(o,"p1",c,discord_webhook_url="https://discord.com/api/webhooks/1/abc"))
    assert o.get("p1").status=="failed"
    assert o.get("p1").attempt_count==1
    with pytest.raises(PermissionError):
        asyncio.run(deliver_approved(o,"p1",c,discord_webhook_url="https://discord.com/api/webhooks/1/abc"))
    assert c.calls==1
