"""One-shot collection with persistent attempt and failure tracking."""
import time
from typing import Any, Callable
from .collector import collect_once
from .collector_state import CollectorStateStore
from .quote_archive import QuoteArchive

async def collect_with_state(client: Any, archive: QuoteArchive,
                             state: CollectorStateStore, *, pair: str,
                             clock: Callable[[], float] = time.time,
                             min_interval_seconds: float = 60,
                             max_failures: int = 3) -> dict:
    if pair not in ("XBTUSD","ETHUSD"):
        raise ValueError("Unsupported pair")
    now=clock()
    if not state.record_attempt("kraken",pair,now,min_interval_seconds):
        raise RuntimeError("Collector stopped or rate-limited")
    try:
        result=await collect_once(client,archive,pair=pair,clock=clock)
    except Exception:
        state.record_result("kraken",pair,False,max_failures)
        raise
    state.record_result("kraken",pair,True,max_failures)
    return result
