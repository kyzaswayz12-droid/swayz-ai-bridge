from decimal import Decimal as D
import pytest
from trading.market_data import Candle
from trading.research import research_backtest

def test_research_backtest_discloses_simulation():
    prices=[10,9,8,7,6,7,8,9,10,11,12,13]
    bars=[Candle(float(i),D(v),D(v),D(v),D(v),D("1")) for i,v in enumerate(prices,start=1)]
    report=research_backtest(bars,short_window=2,long_window=4)
    assert report["mode"]=="PAPER_BACKTEST"
    assert report["bars_evaluated"]==12
    assert report["verified_live_performance"] is False

def test_research_rejects_short_history():
    with pytest.raises(ValueError):
        research_backtest([])
