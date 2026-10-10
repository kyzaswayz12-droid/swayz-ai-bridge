from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger
from trading.equity_state import ensure_equity_state
from trading.equity_observation import observe_equity
from trading.kill_switch import initialise_kill_switch,set_kill_switch
from trading.risk_state_check import verify_risk_state

def test_risk_state_validation():
    ledger=TransactionalPaperLedger()
    ensure_equity_state(ledger,D("1000"))
    initialise_kill_switch(ledger)
    set_kill_switch(ledger,False)
    observe_equity(ledger,D("1100"))
    assert verify_risk_state(ledger,D("1050"))["state"]=="validated"
    with pytest.raises(ValueError,match="peak"):
        verify_risk_state(ledger,D("1200"))
    ledger.close()

def test_disabled_account_cannot_pass_risk_state_check():
    ledger=TransactionalPaperLedger()
    ensure_equity_state(ledger,D("1000"))
    initialise_kill_switch(ledger)
    with pytest.raises(ValueError,match="kill switch"):
        verify_risk_state(ledger,D("1000"))
    ledger.close()
