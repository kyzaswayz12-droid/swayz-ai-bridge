from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger
from trading.kill_switch import initialise_kill_switch,set_kill_switch,assert_paper_enabled

def test_kill_switch_persists_across_restart(tmp_path):
    path=str(tmp_path/"paper.db")
    l=TransactionalPaperLedger(path)
    initialise_kill_switch(l)
    with pytest.raises(ValueError,match="disabled"):
        assert_paper_enabled(l)
    set_kill_switch(l,False)
    assert_paper_enabled(l)
    l.close()
    l=TransactionalPaperLedger(path)
    assert_paper_enabled(l)
    set_kill_switch(l,True)
    with pytest.raises(ValueError,match="disabled"):
        assert_paper_enabled(l)
    l.close()

def test_missing_control_state_fails_closed():
    l=TransactionalPaperLedger()
    with pytest.raises(ValueError):
        assert_paper_enabled(l)
    l.close()
