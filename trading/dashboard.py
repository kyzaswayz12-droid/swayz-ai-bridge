"""Public-safe, read-only paper trading dashboard projections.

No account balances, subscriber identities, credentials or live order access.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from .journal import PaperJournal

@dataclass(frozen=True)
class PublicPaperSummary:
    mode: str
    fill_count: int
    instruments: tuple[str, ...]
    total_reported_fees: str
    performance_verified: bool

def paper_summary(journal: PaperJournal) -> PublicPaperSummary:
    fills=[e for e in journal.events() if e["kind"]=="fill"]
    instruments=tuple(sorted({str(e["payload"].get("symbol","")) for e in fills
                              if e["payload"].get("symbol")}))
    fees=Decimal("0")
    for event in fills:
        fee=Decimal(str(event["payload"].get("fee","0")))
        if not fee.is_finite() or fee < 0:
            raise ValueError("Invalid journal fee")
        fees+=fee
    return PublicPaperSummary(
        mode="PAPER_SIMULATION",
        fill_count=len(fills),
        instruments=instruments,
        total_reported_fees=str(fees),
        performance_verified=False,
    )

def public_payload(summary: PublicPaperSummary) -> dict:
    return {
        "mode": summary.mode,
        "fill_count": summary.fill_count,
        "instruments": list(summary.instruments),
        "total_reported_fees": summary.total_reported_fees,
        "performance_verified": summary.performance_verified,
        "notice": "Simulated activity only; not verified investment performance.",
    }
