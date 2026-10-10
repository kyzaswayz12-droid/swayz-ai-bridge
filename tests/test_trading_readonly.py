import sqlite3
import pytest
from trading.journal import PaperJournal
from trading.readonly import ReadOnlyPaperJournal

def test_read_only_snapshot_preserves_data(tmp_path):
    path=str(tmp_path/"snapshot.db")
    writer=PaperJournal(path)
    writer.append("f1","fill",{"symbol":"BTC/USD","fee":"0.1"})
    writer.close()
    reader=ReadOnlyPaperJournal(path)
    assert reader.events()[0]["event_id"]=="f1"
    with pytest.raises(sqlite3.OperationalError):
        reader.conn.execute("DELETE FROM paper_events")
    reader.close()

def test_missing_snapshot_is_not_created(tmp_path):
    path=tmp_path/"missing.db"
    with pytest.raises(FileNotFoundError):
        ReadOnlyPaperJournal(str(path))
    assert not path.exists()
