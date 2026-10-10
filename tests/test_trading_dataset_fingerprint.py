from decimal import Decimal as D
from trading.market_data import Candle
from trading.dataset_fingerprint import candle_fingerprint

def bar(price):
    p=D(str(price))
    return Candle(100.0,p,p,p,p,D("1"))

def test_dataset_fingerprint_changes_with_price():
    first=candle_fingerprint([bar(100)])
    assert first==candle_fingerprint([bar(100)])
    assert first!=candle_fingerprint([bar(101)])
    assert len(first)==64
