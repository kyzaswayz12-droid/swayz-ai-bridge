from decimal import Decimal as D
import pytest
from trading.market_data import Candle, validate_candles, replay_quotes

def bar(ts, close=D("100")):
    return Candle(ts, close, close, close, close, D("10"))

def test_replay_spread():
    q=list(replay_quotes([bar(1),bar(2)]))
    assert len(q)==2
    assert q[0].bid==D("99.9500")
    assert q[0].ask==D("100.0500")

def test_out_of_order_rejected():
    with pytest.raises(ValueError):
        validate_candles([bar(2),bar(1)])

def test_non_finite_rejected():
    with pytest.raises(ValueError):
        validate_candles([bar(1,D("NaN"))])

def test_bad_spread_rejected():
    with pytest.raises(ValueError):
        list(replay_quotes([bar(1)],D("-0.01")))
