from decimal import Decimal as D
from trading.market_data import Candle
from trading.signal_study import study_signals

def test_study_reports_counts_not_profit():
    values=[10,9,8,7,6,7,8,9,10,11,12,13]
    candles=[Candle(float(i),D(v),D(v),D(v),D(v),D("1")) for i,v in enumerate(values,start=1)]
    result=study_signals(candles,short_window=2,long_window=4)
    assert result.bars==len(values)
    assert result.buy_signals>=1
    assert result.performance_calculated is False
