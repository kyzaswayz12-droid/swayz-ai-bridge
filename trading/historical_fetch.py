"""Read-only public Kraken OHLC fetcher with bounded intervals."""
from typing import Any
import time
from .history_integrity import completed_candles
from .kraken_ohlc import parse_kraken_ohlc, HistoricalDataError

SUPPORTED_INTERVALS=frozenset({1,5,15,60,240,1440})

async def fetch_kraken_ohlc(client: Any, *, pair: str, interval: int=60, observed_at: float | None=None):
    if pair not in ("XBTUSD","ETHUSD") or interval not in SUPPORTED_INTERVALS:
        raise HistoricalDataError("Unsupported pair or interval")
    response=await client.get(
        "https://api.kraken.com/0/public/OHLC",
        params={"pair":pair,"interval":interval},timeout=15)
    response.raise_for_status()
    bars=parse_kraken_ohlc(response.json(),pair=pair)
    return completed_candles(bars,interval_seconds=interval*60,
                             observed_at=time.time() if observed_at is None else observed_at)
