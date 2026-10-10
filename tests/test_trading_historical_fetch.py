import asyncio
from trading.historical_fetch import fetch_kraken_ohlc

class Response:
    def raise_for_status(self): pass
    def json(self):
        return {"error":[],"result":{"XXBTZUSD":[
            [100,"10","12","9","11","10.5","5",4]],"last":100}}
class Client:
    def __init__(self): self.calls=[]
    async def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return Response()

def test_historical_fetch_is_public_and_read_only():
    c=Client()
    bars=asyncio.run(fetch_kraken_ohlc(c,pair="XBTUSD",interval=60))
    assert len(bars)==1
    assert c.calls[0][0].endswith("/0/public/OHLC")
    assert c.calls[0][1]["params"]["interval"]==60
