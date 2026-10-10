from decimal import Decimal as D
import pytest
from trading.engine import Instrument,Market,Order,Quote
from trading.transactional_ledger import TransactionalPaperLedger
from trading.equity_state import ensure_equity_state,read_equity_state
from trading.kill_switch import initialise_kill_switch,set_kill_switch
from trading.locked_execution import submit_locked

BTC=Instrument("BTC/USD",Market.CRYPTO,"USD")

def prepare():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("1000"))
    ensure_equity_state(l,D("900"))
    initialise_kill_switch(l)
    set_kill_switch(l,False)
    return l

def attempt(l,quantity):
    return submit_locked(
        l,Order("o1",BTC,"buy",D(quantity)),
        quotes={"BTC/USD":Quote(D("99.9"),D("100"),100)},
        quote_currency={"BTC/USD":"USD"},
        fx_to_base={"USD":D("1")},now=101)

def test_successful_fill_updates_peak_within_transaction():
    l=prepare()
    attempt(l,"1")
    assert read_equity_state(l)==(D("900"),D("1000"))
    assert l.position("BTC/USD")==D("1")
    l.close()

def test_failed_order_rolls_back_peak_update():
    l=prepare()
    with pytest.raises(ValueError,match="Order notional"):
        attempt(l,"20")
    assert read_equity_state(l)==(D("900"),D("900"))
    assert l.position("BTC/USD")==0
    l.close()
