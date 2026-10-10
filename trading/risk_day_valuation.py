"""Valuation-derived paper risk day rollover under a single SQLite lock.

No real-money execution or unattended scheduler.
"""
from datetime import datetime
from decimal import Decimal
from .transactional_ledger import TransactionalPaperLedger
from .valuation import value_portfolio
from .quote_policy import validate_quote_for_paper
from .equity_state import read_equity_state
from .kill_switch import assert_paper_enabled
from .engine import Quote

def rollover_from_ledger(ledger: TransactionalPaperLedger, *, new_day: str,
                         quotes: dict[str, Quote], quote_currency: dict[str,str],
                         fx_to_base: dict[str,Decimal], now: float) -> bool:
    requested=datetime.strptime(new_day,"%Y-%m-%d").date()
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        assert_paper_enabled(ledger)
        row=ledger.conn.execute("SELECT utc_day FROM paper_risk_day WHERE id=1").fetchone()
        if not row:
            raise ValueError("Risk day state missing")
        current=datetime.strptime(row[0],"%Y-%m-%d").date()
        if requested < current:
            raise ValueError("Cannot roll risk day backwards")
        if requested == current:
            ledger.conn.execute("COMMIT")
            return False
        for symbol,quantity in ledger.conn.execute("SELECT symbol,quantity FROM positions"):
            if Decimal(quantity)>0:
                quote=quotes.get(symbol)
                if quote is None:
                    raise ValueError("Missing position quote")
                validate_quote_for_paper(quote,now)
        equity,_=value_portfolio(ledger,quotes=quotes,quote_currency=quote_currency,
                                 fx_to_base=fx_to_base)
        if not equity.is_finite() or equity<=0:
            raise ValueError("Invalid derived equity")
        _,peak=read_equity_state(ledger)
        ledger.conn.execute(
            "UPDATE paper_equity_state SET day_start_equity=?,peak_equity=? WHERE id=1",
            (str(equity),str(max(peak,equity))))
        ledger.conn.execute("UPDATE paper_risk_day SET utc_day=? WHERE id=1",(new_day,))
        ledger.conn.execute("COMMIT")
        return True
    except BaseException:
        ledger.conn.execute("ROLLBACK")
        raise
