"""Record validated paper-equity observations without weakening risk limits.

The day-start reference is immutable here; a separate, audited day-rollover
operation will be required before unattended paper trading.
"""
from decimal import Decimal
from .transactional_ledger import TransactionalPaperLedger
from .equity_state import read_equity_state

def observe_equity(ledger: TransactionalPaperLedger, equity: Decimal) -> tuple[Decimal, Decimal]:
    if not equity.is_finite() or equity < 0:
        raise ValueError("Invalid equity observation")
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        day_start, peak = read_equity_state(ledger)
        if not all(v.is_finite() and v > 0 for v in (day_start, peak)):
            raise ValueError("Invalid equity reference state")
        new_peak = max(peak, equity)
        ledger.conn.execute(
            "UPDATE paper_equity_state SET peak_equity=? WHERE id=1",
            (str(new_peak),))
        ledger.conn.execute("COMMIT")
        return day_start, new_peak
    except BaseException:
        ledger.conn.execute("ROLLBACK")
        raise
