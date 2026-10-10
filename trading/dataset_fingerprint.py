"""Canonical fingerprint of validated historical candles."""
import hashlib
import json
from .market_data import Candle, validate_candles

def candle_fingerprint(candles: list[Candle]) -> str:
    bars=validate_candles(candles)
    rows=[
        [bar.timestamp,str(bar.open),str(bar.high),str(bar.low),
         str(bar.close),str(bar.volume)]
        for bar in bars
    ]
    payload=json.dumps(rows,separators=(",",":"),ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
