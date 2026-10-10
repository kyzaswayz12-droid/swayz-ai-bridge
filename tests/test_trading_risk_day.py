from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger
from trading.equity_state import ensure_equity_state,read_equity_state
from trading.kill_switch import initialise_kill_switch,set_kill_switch
from trading.risk_day import initialise_risk_day,rollover_risk_day

def prepare():
    l=TransactionalPaperLedger()
    ensure_equity_state(l,D("1000"))
    initialise_kill_switch(l)
    set_kill_switch(l,False)
    initialise_risk_day(l,"2026-10-09")
    return l

def test_rollover_changes_daily_start_but_preserves_peak():
    l=prepare()
    assert rollover_risk_day(l,new_day="2026-10-10",observed_equity=D("950"))
    assert read_equity_state(l)==(D("950"),D("1000"))
    assert not rollover_risk_day(l,new_day="2026-10-10",observed_equity=D("100"))
    assert read_equity_state(l)==(D("950"),D("1000"))
    l.close()

def test_backwards_rollover_fails():
    l=prepare()
    with pytest.raises(ValueError,match="backwards"):
        rollover_risk_day(l,new_day="2026-10-08",observed_equity=D("900"))
    assert read_equity_state(l)==(D("1000"),D("1000"))
    l.close()

def test_disabled_rollover_rejected():
    l=prepare()
    set_kill_switch(l,True)
    with pytest.raises(ValueError,match="kill switch"):
        rollover_risk_day(l,new_day="2026-10-10",observed_equity=D("900"))
    l.close()
