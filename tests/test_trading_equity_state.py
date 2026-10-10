from decimal import Decimal as D
from trading.transactional_ledger import TransactionalPaperLedger
from trading.equity_state import ensure_equity_state,read_equity_state

def test_equity_reference_state_is_persistent(tmp_path):
    path=str(tmp_path/"ledger.db")
    l=TransactionalPaperLedger(path)
    ensure_equity_state(l,D("1000"))
    assert read_equity_state(l)==(D("1000"),D("1000"))
    l.close()
    l=TransactionalPaperLedger(path)
    assert read_equity_state(l)==(D("1000"),D("1000"))
    l.close()
