"""Regression tests for locked paper execution safety boundaries."""
from decimal import Decimal as D
import pytest
from trading.engine import Instrument, Market, Order, Quote
from trading.transactional_ledger import TransactionalPaperLedger
from trading.equity_state import ensure_equity_state
from trading.kill_switch import initialise_kill_switch, set_kill_switch
from trading.locked_execution import submit_locked

BTC=Instrument("BTC/USD",Market.CRYPTO,"USD")
QUOTES={"BTC/USD":Quote(D("99.9"),D("100"),100)}

def create():
    ledger=TransactionalPaperLedger()
    ledger.deposit_opening_cash("USD",D("1000"))
    ensure_equity_state(ledger,D("1000"))
    initialise_kill_switch(ledger)
    return ledger

def send(ledger,order_id="test",now=101,quotes=None):
    return submit_locked(
        ledger,Order(order_id,BTC,"buy",D("1")),
        quotes=QUOTES if quotes is None else quotes,
        quote_currency={"BTC/USD":"USD"},
        fx_to_base={"USD":D("1")},now=now)

def test_default_kill_switch_blocks_order():
    ledger=create()
    with pytest.raises(ValueError,match="kill switch"):
        send(ledger)
    assert ledger.balance("USD")==D("1000")
    assert ledger.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]==0
    ledger.close()

def test_stale_quote_blocks_order():
    ledger=create()
    set_kill_switch(ledger,False)
    with pytest.raises(ValueError,match="Stale"):
        send(ledger,now=200)
    assert ledger.balance("USD")==D("1000")
    ledger.close()

def test_duplicate_order_rolls_back():
    ledger=create()
    set_kill_switch(ledger,False)
    send(ledger)
    with pytest.raises(ValueError,match="Duplicate"):
        send(ledger)
    assert ledger.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]==1
    ledger.close()
