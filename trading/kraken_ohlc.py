"""Parse Kraken public OHLC candle payloads into validated historical bars."""
from decimal import Decimal, InvalidOperation
from typing import Any
from .market_data import Candle, validate_candles

class HistoricalDataError(ValueError):
    pass

def parse_kraken_ohlc(payload: dict[str, Any], *, pair: str) -> list[Candle]:
    if pair not in ("XBTUSD","ETHUSD"):
        raise HistoricalDataError("Unsupported pair")
    if not isinstance(payload,dict) or payload.get("error") != []:
        raise HistoricalDataError("Exchange OHLC error")
    result=payload.get("result")
    if not isinstance(result,dict):
        raise HistoricalDataError("Invalid OHLC result")
    keys=[key for key in result if key!="last"]
    if len(keys)!=1 or not isinstance(result[keys[0]],list):
        raise HistoricalDataError("Ambiguous OHLC pair")
    bars=[]
    for row in result[keys[0]]:
        if not isinstance(row,list) or len(row)<8:
            raise HistoricalDataError("Malformed OHLC row")
        try:
            bars.append(Candle(
                timestamp=float(row[0]),
                open=Decimal(str(row[1])),
                high=Decimal(str(row[2])),
                low=Decimal(str(row[3])),
                close=Decimal(str(row[4])),
                volume=Decimal(str(row[6])),
            ))
        except (ValueError,TypeError,InvalidOperation) as exc:
            raise HistoricalDataError("Invalid OHLC value") from exc
    try:
        return validate_candles(bars)
    except ValueError as exc:
        raise HistoricalDataError("Invalid candle sequence") from exc
