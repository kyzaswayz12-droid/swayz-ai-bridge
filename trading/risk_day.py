"""Explicit UTC day rollover for paper risk reference state.

Only an operator-authorised maintenance process should invoke this.
"""
from datetime import datetime, timezone
from decimal import Decimal
from .transactional_ledger import TransactionalPaperLedger
from .equity_state import read_equity_state
from .kill_switch import assert_paper_enabled

def initialise_risk_day(ledger: TransactionalPaperLedger, day: str) -> None:
    datetime.strptime(day,"%Y-%m-%d")
    ledger.conn.execute("""CREATE TABLE IF NOT EXISTS paper_risk_day(
        id INTEGER PRIMARY KEY CHECK(id=1),
        utc_day TEXT NOT NULL
    )""")
    ledger.conn.execute("INSERT OR IGNORE INTO paper_risk_day(id,utc_day) VALUES(1,?)",(day,))

def rollover_risk_day(ledger: TransactionalPaperLedger, *, new_day: str,
                      observed_equity: Decimal) -> bool:
    parsed=datetime.strptime(new_day,"%Y-%m-%d").date()
    if not observed_equity.is_finite() or observed_equity <= 0:
        raise ValueError("Invalid rollover equity")
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        assert_paper_enabled(ledger)
        row=ledger.conn.execute("SELECT utc_day FROM paper_risk_day WHERE id=1").fetchone()
        if not row:
            raise ValueError("Risk day state missing")
        previous=datetime.strptime(row[0],"%Y-%m-%d").date()
        if parsed < previous:
            raise ValueError("Cannot roll risk day backwards")
        if parsed == previous:
            ledger.conn.execute("COMMIT")
            return False
        day_start,peak=read_equity_state(ledger)
        if observed_equity > peak:
            peak=observed_equity
        ledger.conn.execute("UPDATE paper_equity_state SET day_start_equity=?,peak_equity=? WHERE id=1",
                            (str(observed_equity),str(peak)))
        ledger.conn.execute("UPDATE paper_risk_day SET utc_day=? WHERE id=1",(new_day,))
        ledger.conn.execute("COMMIT")
        return True
    except BaseException:
        ledger.conn.execute("ROLLBACK")
        raise
