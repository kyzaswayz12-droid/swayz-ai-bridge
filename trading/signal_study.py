"""Deterministic, no-trade backtest summary for research signals.

This stage measures signal counts only; it does not claim performance.
"""
from dataclasses import dataclass
from .market_data import Candle
from .strategy import moving_average_signals

@dataclass(frozen=True)
class SignalStudy:
    bars: int
    evaluated_points: int
    buy_signals: int
    sell_signals: int
    hold_signals: int
    performance_calculated: bool = False

def study_signals(candles: list[Candle],short_window: int=5,long_window: int=20) -> SignalStudy:
    signals=moving_average_signals(candles,short_window=short_window,long_window=long_window)
    return SignalStudy(
        bars=len(candles),
        evaluated_points=len(signals),
        buy_signals=sum(x.signal=="buy_signal" for x in signals),
        sell_signals=sum(x.signal=="sell_signal" for x in signals),
        hold_signals=sum(x.signal=="hold" for x in signals))
