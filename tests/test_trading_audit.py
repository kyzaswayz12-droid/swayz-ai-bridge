from trading.audit import journal_fingerprint
from trading.journal import PaperJournal

def test_fingerprint_is_stable_and_detects_changes():
    j=PaperJournal()
    empty=journal_fingerprint(j)
    assert empty==journal_fingerprint(j)
    j.append("fill:1","fill",{"symbol":"BTC/USD","price":"100"})
    first=journal_fingerprint(j)
    assert first["sha256"]!=empty["sha256"]
    assert first["event_count"]==1
    assert first==journal_fingerprint(j)
    j.close()
