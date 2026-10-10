from decimal import Decimal as D
from trading.collector_status import collector_status
from trading.collector_state import CollectorStateStore
from trading.quote_archive import QuoteArchive
from trading.engine import Quote

def test_collector_status_without_credentials():
    state=CollectorStateStore()
    archive=QuoteArchive()
    state.record_attempt("kraken","XBTUSD",100,60)
    archive.record("kraken","XBTUSD",Quote(D("100"),D("101"),100),101)
    status=collector_status(state,archive,"kraken","XBTUSD")
    assert status.quote_count==1
    assert status.last_quote_timestamp==100
    assert status.consecutive_failures==0
    state.close()
    archive.close()
