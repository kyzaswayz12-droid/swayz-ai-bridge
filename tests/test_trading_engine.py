from decimal import Decimal as D
import pytest
from trading.engine import Instrument, Market, Order, Quote, PaperAccount

BTC = Instrument("BTC/USD", Market.CRYPTO, "USD")
def test_buy_and_sell_accounting():
    a = PaperAccount()
    buy = a.execute(Order("1", BTC, "buy", D("0.01")), Quote(D("99"), D("100"), 10), 11)
    assert buy.fee == D("0.001")
    assert a.balances["USD"] == D("9998.999")
    a.execute(Order("2", BTC, "sell", D("0.01")), Quote(D("110"), D("111"), 12), 13)
    assert a.positions["BTC/USD"] == 0
    assert a.balances["USD"] == D("10000.0979")

@pytest.mark.parametrize("order,quote,now", [
    (Order("1", BTC, "buy", D("-1")), Quote(D("99"), D("100"), 10), 11),
    (Order("1", BTC, "buy", D("1")), Quote(D("99"), D("100"), 10), 100),
    (Order("1", BTC, "sell", D("1")), Quote(D("99"), D("100"), 10), 11),
    (Order("1", BTC, "buy", D("11")), Quote(D("99"), D("100"), 10), 11),
])
def test_rejected_orders_do_not_mutate_state(order, quote, now):
    a = PaperAccount()
    with pytest.raises(ValueError):
        a.execute(order, quote, now)
    assert not a.fills
    assert a.balances["USD"] == D("10000")

def test_duplicate_id_rejected():
    a = PaperAccount()
    order = Order("one", BTC, "buy", D("1"))
    a.execute(order, Quote(D("99"), D("100"), 10), 11)
    with pytest.raises(ValueError, match="duplicate"):
        a.execute(order, Quote(D("99"), D("100"), 10), 11)

def test_currency_isolation():
    a = PaperAccount()
    eur = Instrument("EUR/USD", Market.FOREX, "EUR")
    with pytest.raises(ValueError, match="Insufficient"):
        a.execute(Order("fx", eur, "buy", D("1")), Quote(D("10"), D("11"), 10), 11)
