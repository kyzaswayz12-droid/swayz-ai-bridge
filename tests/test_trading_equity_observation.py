from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger
from trading.equity_state import ensure_equity_state, read_equity_state
from trading.equity_observation import observe_equity

def test_peak_never_decreases_and_day_start_is_stable(tmp_path):
    path=str(tmp_path/"paper.db")
    ledger=TransactionalPaperLedger(path)
    ensure_equity_state(ledger,D("1000"))
    assert observe_equity(ledger,D("1100"))==(D("1000"),D("1100"))
    assert observe_equity(ledger,D("900"))==(D("1000"),D("1100"))
    ledger.close()
    ledger=TransactionalPaperLedger(path)
    assert read_equity_state(ledger)==(D("1000"),D("1100"))
    ledger.close()

def test_invalid_observation_does_not_mutate_state():
    ledger=TransactionalPaperLedger()
    ensure_equity_state(ledger,D("1000"))
    with pytest.raises(ValueError):
        observe_equity(ledger,D("NaN"))
    assert read_equity_state(ledger)==(D("1000"),D("1000"))
    ledger.close()

def test_missing_reference_fails_closed():
    ledger=TransactionalPaperLedger()
    with pytest.raises(ValueError,match="reference"):
        observe_equity(ledger,D("1000"))
    ledger.close()
