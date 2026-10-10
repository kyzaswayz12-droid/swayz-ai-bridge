from decimal import Decimal as D
from concurrent.futures import ThreadPoolExecutor
import pytest
from trading.engine import Instrument, Market, Order, Quote
from trading.transactional_ledger import TransactionalPaperLedger
from trading.equity_state import ensure_equity_state
from trading.locked_execution import submit_locked

BTC = Instrument("BTC/USD", Market.CRYPTO, "USD")
QUOTES = {"BTC/USD": Quote(D("99.9"), D("100"), 100)}
CURRENCIES = {"BTC/USD": "USD"}
FX = {"USD": D("1")}

def setup(path=":memory:", opening=D("1000")):
    ledger=TransactionalPaperLedger(path)
    ledger.deposit_opening_cash("USD",opening)
    ensure_equity_state(ledger,opening)
    return ledger

def submit(ledger, order_id, qty):
    return submit_locked(
        ledger, Order(order_id,BTC,"buy",D(qty)), quotes=QUOTES,
        quote_currency=CURRENCIES, fx_to_base=FX, now=101)

def test_locked_execution_derives_exposure_from_ledger():
    ledger=setup()
    submit(ledger,"one","3")
    assert ledger.position("BTC/USD")==D("3")
    with pytest.raises(ValueError,match="Gross exposure"):
        submit(ledger,"two","3")
    assert ledger.position("BTC/USD")==D("3")
    assert ledger.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]==1
    ledger.close()

def test_two_connections_cannot_both_exceed_exposure(tmp_path):
    path=str(tmp_path/"locked.db")
    first=setup(path)
    def worker(oid):
        connection=TransactionalPaperLedger(path)
        try:
            return submit(connection,oid,"3")
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(worker,oid) for oid in ("a","b")]
        outcomes=[]
        for f in futures:
            try:
                outcomes.append(f.result())
            except ValueError:
                pass
    assert len(outcomes)==1
    assert first.position("BTC/USD")==D("3")
    assert first.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]==1
    first.close()

def test_missing_reference_state_rolls_back():
    ledger=TransactionalPaperLedger()
    ledger.deposit_opening_cash("USD",D("1000"))
    with pytest.raises(ValueError,match="reference state"):
        submit(ledger,"one","1")
    assert ledger.balance("USD")==D("1000")
    ledger.close()
