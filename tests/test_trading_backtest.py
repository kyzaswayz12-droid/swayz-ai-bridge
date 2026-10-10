from decimal import Decimal as D
from trading.market_data import Candle
from trading.backtest import backtest_crossover

def bar(i,p):
    v=D(str(p))
    return Candle(float(i),v,v,v,v,D("100"))

def test_no_future_signal_execution():
    values=[10,9,8,7,6,7,8,9,10,11,12,13]
    bars=[bar(i,p) for i,p in enumerate(values,start=1)]
    early=backtest_crossover(bars[:7],short_window=2,long_window=4)
    later=backtest_crossover(bars,short_window=2,long_window=4)
    assert early.trades==0
    assert later.trades>=1
    assert later.mode=="PAPER_BACKTEST"

def test_flat_market_no_trades_or_fees():
    bars=[bar(i,100) for i in range(1,30)]
    result=backtest_crossover(bars)
    assert result.trades==0
    assert result.fees_paid==0
    assert result.final_equity==D("10000")

def test_spread_and_fees_reduce_equity():
    values=[10,9,8,7,6,7,8,9,10,11,12,13]
    bars=[bar(i,p) for i,p in enumerate(values,start=1)]
    free=backtest_crossover(bars,short_window=2,long_window=4,
                            spread_fraction=D("0"),fee_fraction=D("0"))
    costly=backtest_crossover(bars,short_window=2,long_window=4,
                              spread_fraction=D("0.01"),fee_fraction=D("0.01"))
    assert costly.final_equity < free.final_equity
    assert costly.fees_paid > 0
