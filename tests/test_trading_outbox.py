import pytest
from trading.outbox import PublicationOutbox

TEXT="PAPER TRADE — SIMULATED, NOT REAL MONEY\nBTC/USD paper buy"

def test_approval_and_delivery_lifecycle(tmp_path):
    path=str(tmp_path/"outbox.db")
    o=PublicationOutbox(path)
    o.create_draft("pub1","telegram",TEXT)
    assert not o.claim("pub1")
    with pytest.raises(PermissionError):
        o.approve("pub1","stranger",{"owner"})
    assert o.approve("pub1","owner",{"owner"})
    assert o.claim("pub1")
    assert not o.claim("pub1")
    o.close()
    o=PublicationOutbox(path)
    assert o.get("pub1").status=="sending"
    assert o.get("pub1").attempt_count==1
    assert o.mark_sent("pub1")
    assert not o.mark_sent("pub1")
    assert o.get("pub1").status=="sent"
    o.close()

def test_unlabelled_trade_rejected():
    o=PublicationOutbox()
    with pytest.raises(ValueError):
        o.create_draft("pub2","discord","BUY BTC NOW")
    assert o.get("pub2") is None
    o.close()

def test_failed_delivery_requires_manual_review():
    o=PublicationOutbox()
    o.create_draft("pub3","discord",TEXT)
    assert o.approve("pub3","owner",{"owner"})
    assert o.claim("pub3")
    assert o.mark_failed("pub3")
    assert not o.claim("pub3")
    assert o.get("pub3").status=="failed"
    o.close()
