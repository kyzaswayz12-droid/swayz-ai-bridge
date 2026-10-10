from decimal import Decimal as D
import pytest
from trading.kraken_ohlc import parse_kraken_ohlc, HistoricalDataError

def test_kraken_ohlc_parser():
    payload={"error":[],"result":{"XXBTZUSD":[
        [100,"10","12","9","11","10.5","5",4],
        [160,"11","13","10","12","11.5","6",5]],"last":160}}
    bars=parse_kraken_ohlc(payload,pair="XBTUSD")
    assert len(bars)==2
    assert bars[0].close==D("11")
    assert bars[1].volume==D("6")

def test_out_of_order_ohlc_rejected():
    payload={"error":[],"result":{"XXBTZUSD":[
        [160,"10","12","9","11","10.5","5",4],
        [100,"11","13","10","12","11.5","6",5]],"last":160}}
    with pytest.raises(HistoricalDataError):
        parse_kraken_ohlc(payload,pair="XBTUSD")
