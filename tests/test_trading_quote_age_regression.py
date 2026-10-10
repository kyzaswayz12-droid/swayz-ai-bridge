from decimal import Decimal as D
import pytest
from trading.engine import Instrument, Market, Order, Quote, RiskLimits
from trading.transactional_ledger import TransactionalPaperLedger
from trading.equity_state import ensure_equity_state
from trading.kill_switch import initialise_kill_switch,set_kill_switch
from trading.locked_execution import submit_locked

BTC=Instrument("BTC/USD",Market.CRYPTO,"USD")

def test_configured_one_second_quote_age_rejected():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("1000"))
    ensure_equity_state(l,D("1000"))
    initialise_kill_switch(l)
    set_kill_switch(l,False)
    with pytest.raises(ValueError,match="Stale"):
        submit_locked(
            l,Order("old",BTC,"buy",D("1")),
            quotes={"BTC/USD":Quote(D("99.9"),D("100"),100)},
            quote_currency={"BTC/USD":"USD"},
            fx_to_base={"USD":D("1")},now=108,
            limits=RiskLimits(max_quote_age_seconds=1))
    assert l.balance("USD")==D("1000")
    assert l.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]==0
    l.close()
