from decimal import Decimal as D
import pytest
from trading.publish import TradeUpdate, TradeMode, render_trade_update

def example(mode=TradeMode.PAPER):
    return TradeUpdate("p-1","BTC/USD","crypto","buy",D("0.01"),D("50000"),mode,"2026-10-10T12:00:00Z")

def test_approval_required():
    with pytest.raises(PermissionError):
        render_trade_update(example())

def test_paper_label_is_unambiguous():
    text=render_trade_update(example(),approved=True)
    assert "PAPER TRADE" in text and "SIMULATED" in text
    assert "BTC/USD" in text

def test_live_trade_sharing_disabled():
    with pytest.raises(PermissionError):
        render_trade_update(example(TradeMode.LIVE),approved=True)
