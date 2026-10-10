import asyncio
from trading.collector import collect_once
from trading.quote_archive import QuoteArchive

class Response:
    def raise_for_status(self): pass
    def json(self):
        return {"error":[],"result":{"XXBTZUSD":{"a":["101"],"b":["100"]}}}

class Client:
    async def get(self,*args,**kwargs):
        return Response()

def test_one_shot_collector_records_quote():
    archive=QuoteArchive()
    result=asyncio.run(collect_once(Client(),archive,pair="XBTUSD",clock=lambda:100.0))
    assert result["mode"]=="read_only"
    assert result["bid"]=="100"
    assert len(archive.recent("XBTUSD"))==1
    archive.close()
