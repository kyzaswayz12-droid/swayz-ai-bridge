from decimal import Decimal as D
import pytest
from trading.publish import TradeUpdate, TradeMode
from trading.subscribers import Channel, Publisher

def update():
    return TradeUpdate("paper-123","BTC/USD","crypto","buy",D("0.01"),D("50000"),
                       TradeMode.PAPER,"2026-10-10T12:00:00Z")

def test_requires_authorised_approver():
    p=Publisher({"owner"})
    with pytest.raises(PermissionError):
        p.prepare(update(),Channel.TELEGRAM,"unknown")

def test_dispatch_once():
    p=Publisher({"owner"})
    publication=p.prepare(update(),Channel.DISCORD,"owner")
    messages=[]
    p.dispatch(publication,lambda channel,text:messages.append((channel,text)))
    assert len(messages)==1 and "SIMULATED" in messages[0][1]
    with pytest.raises(ValueError,match="Already"):
        p.dispatch(publication,lambda channel,text:messages.append((channel,text)))
    assert len(messages)==1

def test_failed_send_can_retry():
    p=Publisher({"owner"})
    publication=p.prepare(update(),Channel.TELEGRAM,"owner")
    def fail(channel,text):
        raise ConnectionError("offline")
    with pytest.raises(ConnectionError):
        p.dispatch(publication,fail)
    messages=[]
    p.dispatch(publication,lambda channel,text:messages.append(text))
    assert len(messages)==1
