import asyncio
import pytest
from trading.collector_runner import collect_with_state
from trading.collector_state import CollectorStateStore
from trading.quote_archive import QuoteArchive

class Response:
    def raise_for_status(self): pass
    def json(self): return {"error":[],"result":{"XXBTZUSD":{"a":["101"],"b":["100"]}}}
class GoodClient:
    async def get(self,*args,**kwargs): return Response()
class BadClient:
    async def get(self,*args,**kwargs): raise ConnectionError("offline")

def test_persistent_rate_limit_and_recovery(tmp_path):
    path=str(tmp_path/"state.db")
    state=CollectorStateStore(path)
    archive=QuoteArchive()
    result=asyncio.run(collect_with_state(GoodClient(),archive,state,pair="XBTUSD",clock=lambda:100.0))
    assert result["mode"]=="read_only"
    state.close()
    state=CollectorStateStore(path)
    with pytest.raises(RuntimeError,match="rate-limited"):
        asyncio.run(collect_with_state(GoodClient(),archive,state,pair="XBTUSD",clock=lambda:110.0))
    assert len(archive.recent("XBTUSD"))==1
    state.close()
    archive.close()

def test_repeated_failures_stop_collection():
    state=CollectorStateStore()
    archive=QuoteArchive()
    for n in (100.0,170.0):
        with pytest.raises(ConnectionError):
            asyncio.run(collect_with_state(BadClient(),archive,state,pair="XBTUSD",
                                           clock=lambda value=n:value,max_failures=2))
    assert state.get("kraken","XBTUSD").stopped
    with pytest.raises(RuntimeError):
        asyncio.run(collect_with_state(GoodClient(),archive,state,pair="XBTUSD",clock=lambda:300.0))
    state.close()
    archive.close()
