"""Reproducible, simulation-only strategy research manifest."""
from datetime import datetime, timezone
from .dataset_fingerprint import candle_fingerprint
from .market_data import Candle
from .research import research_backtest

def research_manifest(candles: list[Candle], *, pair: str,
                      interval_minutes: int, short_window: int=5,
                      long_window: int=20) -> dict:
    if pair not in ("XBTUSD","ETHUSD") or interval_minutes not in (1,5,15,60,240,1440):
        raise ValueError("Unsupported dataset")
    report=research_backtest(candles,short_window=short_window,long_window=long_window)
    return {
        "schema_version":1,
        "market_pair":pair,
        "interval_minutes":interval_minutes,
        "dataset_sha256":candle_fingerprint(candles),
        "first_candle_utc":datetime.fromtimestamp(candles[0].timestamp,timezone.utc).isoformat(),
        "last_candle_utc":datetime.fromtimestamp(candles[-1].timestamp,timezone.utc).isoformat(),
        "strategy_parameters":{"short_window":short_window,"long_window":long_window},
        "report":report,
        "source_verification":"not independently verified",
    }
