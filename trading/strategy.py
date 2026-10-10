"""Causal moving-average crossover research signal.

Signals are computed using only bars available at that timestamp.
No orders, execution, or model-generated recommendations.
"""
from dataclasses import dataclass
from decimal import Decimal
from .market_data import Candle, validate_candles

@dataclass(frozen=True)
class StrategySignal:
    timestamp: float
    signal: str
    short_average: Decimal
    long_average: Decimal

def moving_average_signals(candles: list[Candle], *, short_window: int = 5,
                           long_window: int = 20) -> list[StrategySignal]:
    if not isinstance(short_window,int) or not isinstance(long_window,int):
        raise ValueError("Window sizes must be integers")
    if short_window < 2 or long_window <= short_window:
        raise ValueError("Require 2 <= short_window < long_window")
    bars=validate_candles(candles)
    if len(bars) < long_window + 1:
        return []
    closes=[bar.close for bar in bars]
    result=[]
    previous_relation=None
    for index in range(long_window-1,len(bars)):
        short=sum(closes[index-short_window+1:index+1],Decimal("0"))/short_window
        long=sum(closes[index-long_window+1:index+1],Decimal("0"))/long_window
        relation=1 if short>long else (-1 if short<long else 0)
        if previous_relation is None or previous_relation==0 or relation==0:
            action="hold"
        elif previous_relation < 0 and relation > 0:
            action="buy_signal"
        elif previous_relation > 0 and relation < 0:
            action="sell_signal"
        else:
            action="hold"
        result.append(StrategySignal(bars[index].timestamp,action,short,long))
        previous_relation=relation
    return result
