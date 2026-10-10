"""Deterministic historical price replay, paper-only."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from .engine import Quote

@dataclass(frozen=True)
class Candle:
    timestamp: float
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

def validate_candles(candles: Iterable[Candle]) -> list[Candle]:
    result = list(candles)
    previous = None
    for bar in result:
        values = (bar.open, bar.high, bar.low, bar.close, bar.volume)
        if not all(x.is_finite() for x in values):
            raise ValueError("Non-finite candle")
        if bar.low <= 0 or bar.volume < 0 or bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
            raise ValueError("Invalid OHLCV candle")
        if previous is not None and bar.timestamp <= previous:
            raise ValueError("Candles must be strictly chronological")
        previous = bar.timestamp
    return result

def replay_quotes(candles: Iterable[Candle], spread_fraction: Decimal = Decimal("0.001")):
    """Yield close-based synthetic bid/ask quotes; never claim historical executable fills."""
    if not spread_fraction.is_finite() or spread_fraction < 0 or spread_fraction >= 1:
        raise ValueError("Invalid spread")
    for bar in validate_candles(candles):
        half = spread_fraction / 2
        yield Quote(bar.close * (1 - half), bar.close * (1 + half), bar.timestamp)
