"""Bounded market data collection scheduling, with no automatic retries."""
import time
from dataclasses import dataclass
from typing import Callable, Any
from .collector import collect_once
from .quote_archive import QuoteArchive

@dataclass
class CollectorPolicy:
    min_interval_seconds: float = 60
    max_consecutive_failures: int = 3

    def __post_init__(self):
        if self.min_interval_seconds < 10 or self.max_consecutive_failures < 1:
            raise ValueError("Unsafe collector policy")

class CollectorController:
    def __init__(self, policy: CollectorPolicy = None):
        self.policy=policy or CollectorPolicy()
        self.last_attempt: float | None=None
        self.failures=0
        self.stopped=False

    async def attempt(self, client: Any, archive: QuoteArchive, *,
                      pair: str, clock: Callable[[], float] = time.time) -> dict:
        now=clock()
        if self.stopped:
            raise RuntimeError("Collector circuit breaker active")
        if self.last_attempt is not None and now-self.last_attempt < self.policy.min_interval_seconds:
            raise RuntimeError("Collector rate limit")
        self.last_attempt=now
        try:
            result=await collect_once(client,archive,pair=pair,clock=clock)
        except Exception:
            self.failures+=1
            if self.failures >= self.policy.max_consecutive_failures:
                self.stopped=True
            raise
        self.failures=0
        return result
