"""Read-only market quote freshness and paper-order admission checks."""
from dataclasses import dataclass
from decimal import Decimal
from .engine import Quote

@dataclass(frozen=True)
class QuotePolicy:
    max_age_seconds: float = 10
    max_spread_fraction: Decimal = Decimal("0.01")

def validate_quote_for_paper(quote: Quote, now: float, policy: QuotePolicy = QuotePolicy()) -> None:
    if policy.max_age_seconds <= 0:
        raise ValueError("Invalid quote age policy")
    if not policy.max_spread_fraction.is_finite() or not (0 <= policy.max_spread_fraction < 1):
        raise ValueError("Invalid spread policy")
    if not quote.bid.is_finite() or not quote.ask.is_finite() or quote.bid <= 0 or quote.ask < quote.bid:
        raise ValueError("Invalid market quote")
    if now < quote.timestamp or now - quote.timestamp > policy.max_age_seconds:
        raise ValueError("Stale or future market quote")
    spread = (quote.ask - quote.bid) / quote.ask
    if spread > policy.max_spread_fraction:
        raise ValueError("Market spread exceeds paper policy")
