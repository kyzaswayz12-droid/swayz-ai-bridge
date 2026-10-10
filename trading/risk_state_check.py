"""Paper risk-state consistency checks; no automatic repair."""
from decimal import Decimal
from .transactional_ledger import TransactionalPaperLedger
from .equity_state import read_equity_state
from .kill_switch import assert_paper_enabled

def verify_risk_state(ledger: TransactionalPaperLedger, current_equity: Decimal) -> dict:
    if not current_equity.is_finite() or current_equity < 0:
        raise ValueError("Invalid current equity")
    day_start,peak=read_equity_state(ledger)
    if not day_start.is_finite() or not peak.is_finite() or day_start <= 0 or peak <= 0:
        raise ValueError("Invalid stored risk reference")
    assert_paper_enabled(ledger)
    if current_equity > peak:
        raise ValueError("Observed equity exceeds stored peak; update required")
    return {
        "day_start_equity":str(day_start),
        "peak_equity":str(peak),
        "current_equity":str(current_equity),
        "state":"validated",
    }
