"""Validate historical candle completeness and expected spacing."""
from .market_data import Candle, validate_candles

class HistoryIntegrityError(ValueError):
    pass

def completed_candles(candles: list[Candle], *, interval_seconds: int,
                      observed_at: float) -> list[Candle]:
    if interval_seconds <= 0 or observed_at <= 0:
        raise HistoryIntegrityError("Invalid history time settings")
    bars=validate_candles(candles)
    complete=[bar for bar in bars if bar.timestamp + interval_seconds <= observed_at]
    for previous,current in zip(complete,complete[1:]):
        if current.timestamp - previous.timestamp != interval_seconds:
            raise HistoryIntegrityError("Historical candle gap or irregular spacing")
    return complete
