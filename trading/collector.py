"""One-shot, read-only public market-data collection.

Designed to be called by a future supervised scheduler; no continuous polling.
"""
import time
from typing import Any
from .kraken_data import fetch_kraken_quote
from .quote_archive import QuoteArchive

async def collect_once(client: Any, archive: QuoteArchive, *,
                       pair: str, clock=time.time) -> dict:
    observed_at=clock()
    quote=await fetch_kraken_quote(client,pair=pair,observed_at=observed_at)
    archive.record("kraken",pair,quote,now=clock())
    return {
        "source":"kraken",
        "pair":pair,
        "observed_at":quote.timestamp,
        "bid":str(quote.bid),
        "ask":str(quote.ask),
        "mode":"read_only",
    }
