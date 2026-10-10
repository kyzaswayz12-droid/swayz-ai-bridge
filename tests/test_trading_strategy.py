from decimal import Decimal as D
import pytest
from trading.market_data import Candle
from trading.strategy import moving_average_signals

def bar(i,p):
    v=D(str(p))
    return Candle(float(i),v,v,v,v,D("1"))

def test_only_uses_historical_bars():
    bars=[bar(i,p) for i,p in enumerate([10,9,8,7,6,7,8,9,10,11,12,13],start=1)]
    first=moving_average_signals(bars[:8],short_window=2,long_window=4)
    later=moving_average_signals(bars,short_window=2,long_window=4)
    assert first==later[:len(first)]
    assert any(s.signal=="buy_signal" for s in later)

def test_short_history_produces_no_signal():
    assert moving_average_signals([bar(1,10),bar(2,11)],short_window=2,long_window=4)==[]

def test_invalid_windows_rejected():
    with pytest.raises(ValueError):
        moving_average_signals([],short_window=5,long_window=5)
