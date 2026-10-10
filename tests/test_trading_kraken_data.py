import asyncio
from decimal import Decimal as D
import pytest
from trading.kraken_data import fetch_kraken_quote, parse_kraken_ticker, MarketDataError

PAYLOAD={"error":[],"result":{"XXBTZUSD":{"a":["50100","1","1"],"b":["50090","1","1"]}}}

class Response:
    def raise_for_status(self): pass
    def json(self): return PAYLOAD

class Client:
    def __init__(self): self.calls=[]
    async def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return Response()

def test_kraken_quote_parsing():
    q=parse_kraken_ticker(PAYLOAD,pair="XBTUSD",observed_at=100.0)
    assert q.bid==D("50090") and q.ask==D("50100")

def test_adapter_uses_public_read_only_endpoint():
    client=Client()
    q=asyncio.run(fetch_kraken_quote(client,pair="XBTUSD",observed_at=100.0))
    assert q.bid==D("50090")
    assert client.calls[0][0].endswith("/0/public/Ticker")
    assert client.calls[0][1]["params"]=={"pair":"XBTUSD"}

@pytest.mark.parametrize("payload",[
    {"error":["EQuery:Unknown asset pair"],"result":{}},
    {"error":[],"result":{}},
    {"error":[],"result":{"XXBTZUSD":{"a":["1"],"b":["2"]}}},
    {"error":[],"result":{"XXBTZUSD":{"a":["NaN"],"b":["1"]}}},
])
def test_bad_tickers_fail_closed(payload):
    with pytest.raises(MarketDataError):
        parse_kraken_ticker(payload,pair="XBTUSD",observed_at=100.0)

def test_unknown_pair_rejected_before_network():
    client=Client()
    with pytest.raises(MarketDataError):
        asyncio.run(fetch_kraken_quote(client,pair="NOTREAL",observed_at=100.0))
    assert client.calls==[]
