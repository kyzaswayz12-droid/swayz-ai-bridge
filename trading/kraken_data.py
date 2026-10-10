"""Read-only Kraken public ticker adapter. No exchange credentials or orders.

Kraken ticker bid/ask are indicative; they are not guaranteed executable fills.
"""
from decimal import Decimal, InvalidOperation
from typing import Any
from .engine import Quote

KRAKEN_TICKER_URL = "https://api.kraken.com/0/public/Ticker"
SUPPORTED_PAIRS = frozenset({"XBTUSD", "ETHUSD"})

class MarketDataError(ValueError):
    pass

def parse_kraken_ticker(payload: dict[str, Any], *, pair: str, observed_at: float) -> Quote:
    if pair not in SUPPORTED_PAIRS:
        raise MarketDataError("Unsupported market")
    if not isinstance(payload, dict) or payload.get("error") != []:
        raise MarketDataError("Exchange returned an error")
    results = payload.get("result")
    if not isinstance(results, dict) or len(results) != 1:
        raise MarketDataError("Ambiguous ticker response")
    ticker = next(iter(results.values()))
    try:
        bid = Decimal(str(ticker["b"][0]))
        ask = Decimal(str(ticker["a"][0]))
    except (KeyError, IndexError, TypeError, InvalidOperation) as exc:
        raise MarketDataError("Invalid ticker fields") from exc
    if not (bid.is_finite() and ask.is_finite() and Decimal("0") < bid <= ask):
        raise MarketDataError("Invalid bid/ask quote")
    if not isinstance(observed_at, (float, int)) or observed_at <= 0:
        raise MarketDataError("Invalid observation time")
    return Quote(bid=bid, ask=ask, timestamp=float(observed_at))

async def fetch_kraken_quote(client: Any, *, pair: str, observed_at: float) -> Quote:
    if pair not in SUPPORTED_PAIRS:
        raise MarketDataError("Unsupported market")
    response = await client.get(KRAKEN_TICKER_URL, params={"pair": pair}, timeout=10)
    response.raise_for_status()
    return parse_kraken_ticker(response.json(), pair=pair, observed_at=observed_at)
