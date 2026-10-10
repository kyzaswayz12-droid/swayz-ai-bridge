from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger, LedgerFill

def fill(oid="a",side="buy",qty="1",price="100",fee="1"):
    return LedgerFill(oid,"BTC/USD",side,D(qty),D(price),D(fee))

def test_transactional_fill_survives_restart(tmp_path):
    path=str(tmp_path/"ledger.sqlite3")
    l=TransactionalPaperLedger(path)
    l.deposit_opening_cash("USD",D("1000"))
    l.execute(fill(),"USD")
    assert l.balance("USD")==D("899")
    assert l.position("BTC/USD")==D("1")
    l.close()
    l=TransactionalPaperLedger(path)
    assert l.balance("USD")==D("899")
    assert l.position("BTC/USD")==D("1")
    l.execute(fill("b","sell","1","110","1"),"USD")
    assert l.balance("USD")==D("1008")
    assert l.position("BTC/USD")==0
    l.close()

def test_failed_order_rolls_back_everything():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("100"))
    with pytest.raises(ValueError):
        l.execute(fill(qty="2"),"USD")
    assert l.balance("USD")==D("100")
    assert l.position("BTC/USD")==0
    assert l.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]==0
    l.close()

def test_duplicate_order_rejected_without_mutation():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("1000"))
    l.execute(fill(),"USD")
    with pytest.raises(ValueError,match="Duplicate"):
        l.execute(fill(),"USD")
    assert l.balance("USD")==D("899")
    assert l.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]==1
    l.close()
