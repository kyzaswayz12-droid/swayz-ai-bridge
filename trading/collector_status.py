"""Read-only collector operational status projection."""
from dataclasses import dataclass
from .collector_state import CollectorStateStore
from .quote_archive import QuoteArchive

@dataclass(frozen=True)
class MarketCollectorStatus:
    source: str
    pair: str
    stopped: bool
    consecutive_failures: int
    last_attempt: float | None
    quote_count: int
    last_quote_timestamp: float | None

def collector_status(state: CollectorStateStore, archive: QuoteArchive,
                     source: str, pair: str) -> MarketCollectorStatus:
    snapshot=state.get(source,pair)
    quotes=archive.recent(pair,limit=1000)
    return MarketCollectorStatus(
        source=source,pair=pair,stopped=snapshot.stopped,
        consecutive_failures=snapshot.failures,last_attempt=snapshot.last_attempt,
        quote_count=len(quotes),
        last_quote_timestamp=quotes[0]["observed_at"] if quotes else None)
