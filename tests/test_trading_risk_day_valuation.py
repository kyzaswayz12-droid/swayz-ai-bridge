from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger,LedgerFill
from trading.equity_state import ensure_equity_state,read_equity_state
from trading.kill_switch import initialise_kill_switch,set_kill_switch
from trading.risk_day import initialise_risk_day
from trading.risk_day_valuation import rollover_from_ledger
from trading.engine import Quote

def make():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("1000"))
    l.execute(LedgerFill("a","BTC/USD","buy",D("1"),D("100"),D("0")),"USD")
    ensure_equity_state(l,D("1000"))
    initialise_kill_switch(l)
    set_kill_switch(l,False)
    initialise_risk_day(l,"2026-10-09")
    return l

def test_rollover_uses_ledger_equity():
    l=make()
    result=rollover_from_ledger(l,new_day="2026-10-10",
        quotes={"BTC/USD":Quote(D("110"),D("111"),100)},
        quote_currency={"BTC/USD":"USD"},fx_to_base={"USD":D("1")},now=101)
    assert result
    assert read_equity_state(l)==(D("1010"),D("1010"))
    l.close()

def test_missing_quote_does_not_rollover():
    l=make()
    with pytest.raises(ValueError,match="Missing"):
        rollover_from_ledger(l,new_day="2026-10-10",quotes={},
            quote_currency={"BTC/USD":"USD"},fx_to_base={"USD":D("1")},now=101)
    assert read_equity_state(l)==(D("1000"),D("1000"))
    assert l.conn.execute("SELECT utc_day FROM paper_risk_day").fetchone()[0]=="2026-10-09"
    l.close()
