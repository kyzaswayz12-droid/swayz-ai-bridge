from decimal import Decimal
import pytest
from trading.journal import PaperJournal

def test_journal_append_and_replay(tmp_path):
    path = str(tmp_path / "paper.sqlite3")
    journal = PaperJournal(path)
    journal.append("fill-1", "fill", {"qty": Decimal("0.25"), "price": Decimal("125")})
    journal.close()
    reopened = PaperJournal(path)
    assert reopened.events() == [{"sequence": 1, "event_id": "fill-1",
                                  "kind": "fill", "payload": {"price": "125", "qty": "0.25"}}]
    reopened.close()

def test_duplicate_event_is_rejected():
    journal = PaperJournal()
    journal.append("same", "fill", {"qty": "1"})
    with pytest.raises(Exception):
        journal.append("same", "fill", {"qty": "1"})
    assert len(journal.events()) == 1
    journal.close()

def test_invalid_event_does_not_write():
    journal = PaperJournal()
    with pytest.raises(ValueError):
        journal.append("x", "live_order", {})
    assert journal.events() == []
    journal.close()
