import pytest
from trading.journal import PaperJournal
from trading.snapshot import export_public_snapshot
from trading.readonly import ReadOnlyPaperJournal

def test_snapshot_excludes_private_fields(tmp_path):
    journal=PaperJournal()
    journal.append("f1","fill",{
        "symbol":"BTC/USD","side":"buy","quantity":"1","price":"100",
        "fee":"0.1","quote_currency":"USD","api_key":"SECRET","account_id":"PRIVATE"})
    target=tmp_path/"public.db"
    assert export_public_snapshot(journal,str(target))==1
    reader=ReadOnlyPaperJournal(str(target))
    payload=reader.events()[0]["payload"]
    assert payload["symbol"]=="BTC/USD"
    assert "api_key" not in payload
    assert "account_id" not in payload
    reader.close()
    journal.close()

def test_snapshot_refuses_overwrite(tmp_path):
    journal=PaperJournal()
    target=tmp_path/"public.db"
    target.write_text("existing")
    with pytest.raises(FileExistsError):
        export_public_snapshot(journal,str(target))
    assert target.read_text()=="existing"
    journal.close()
