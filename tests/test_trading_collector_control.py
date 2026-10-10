import asyncio
import pytest
from trading.collector_control import CollectorController, CollectorPolicy
from trading.quote_archive import QuoteArchive

class Response:
    def raise_for_status(self): pass
    def json(self): return {"error":[],"result":{"XXBTZUSD":{"a":["101"],"b":["100"]}}}
class Client:
    def __init__(self): self.calls=0
    async def get(self,*args,**kwargs):
        self.calls+=1
        return Response()
class BrokenClient:
    async def get(self,*args,**kwargs):
        raise ConnectionError("offline")

def test_rate_limit():
    c=CollectorController()
    a=QuoteArchive()
    client=Client()
    asyncio.run(c.attempt(client,a,pair="XBTUSD",clock=lambda:100.0))
    with pytest.raises(RuntimeError,match="rate limit"):
        asyncio.run(c.attempt(client,a,pair="XBTUSD",clock=lambda:110.0))
    assert client.calls==1
    a.close()

def test_circuit_breaker():
    c=CollectorController(CollectorPolicy(min_interval_seconds=10,max_consecutive_failures=2))
    a=QuoteArchive()
    for now in (100.0,120.0):
        with pytest.raises(ConnectionError):
            asyncio.run(c.attempt(BrokenClient(),a,pair="XBTUSD",clock=lambda n=now:n))
    assert c.stopped
    with pytest.raises(RuntimeError,match="circuit breaker"):
        asyncio.run(c.attempt(BrokenClient(),a,pair="XBTUSD",clock=lambda:140.0))
    a.close()
