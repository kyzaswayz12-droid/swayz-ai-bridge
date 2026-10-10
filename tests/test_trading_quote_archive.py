from decimal import Decimal as D
import pytest
from trading.engine import Quote
from trading.quote_archive import QuoteArchive

def test_quote_archive_retention(tmp_path):
    path=str(tmp_path/"quotes.db")
    a=QuoteArchive(path,max_rows=2)
    for n in range(3):
        a.record("kraken","XBTUSD",Quote(D("100"),D("100.1"),100+n),101+n)
    assert len(a.recent("XBTUSD"))==2
    assert a.recent("XBTUSD")[0]["observed_at"]==102
    a.close()
    a=QuoteArchive(path,max_rows=2)
    assert len(a.recent("XBTUSD"))==2
    a.close()

def test_stale_quote_not_archived():
    a=QuoteArchive()
    with pytest.raises(ValueError):
        a.record("kraken","XBTUSD",Quote(D("100"),D("101"),1),100)
    assert a.recent("XBTUSD")==[]
    a.close()
