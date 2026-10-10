from decimal import Decimal as D
import pytest
from trading.market_data import Candle
from trading.history_integrity import completed_candles, HistoryIntegrityError

def bar(ts):
    return Candle(float(ts),D("10"),D("11"),D("9"),D("10"),D("1"))

def test_incomplete_latest_candle_removed():
    bars=[bar(0),bar(60),bar(120)]
    result=completed_candles(bars,interval_seconds=60,observed_at=150)
    assert [x.timestamp for x in result]==[0,60]

def test_gap_rejected():
    with pytest.raises(HistoryIntegrityError):
        completed_candles([bar(0),bar(120)],interval_seconds=60,observed_at=300)

def test_exactly_closed_candle_included():
    assert len(completed_candles([bar(60)],interval_seconds=60,observed_at=120))==1
