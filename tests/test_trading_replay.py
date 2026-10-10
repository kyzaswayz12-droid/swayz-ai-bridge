from decimal import Decimal as D
import pytest
from trading.journal import PaperJournal
from trading.replay import replay_portfolio

def test_replay_buy_and_sell():
    j=PaperJournal()
    j.append("f1","fill",{"symbol":"BTC/USD","quote_currency":"USD","side":"buy",
        "quantity":"1","price":"100","fee":"1"})
    j.append("f2","fill",{"symbol":"BTC/USD","quote_currency":"USD","side":"sell",
        "quantity":"1","price":"110","fee":"1"})
    result=replay_portfolio(j,{"USD":D("1000")})
    assert result.balances["USD"]==D("1008")
    assert result.positions["BTC/USD"]==0
    assert result.fill_count==2
    j.close()

def test_replay_rejects_unfunded_trade():
    j=PaperJournal()
    j.append("f1","fill",{"symbol":"BTC/USD","quote_currency":"USD","side":"buy",
        "quantity":"2","price":"100","fee":"0"})
    with pytest.raises(ValueError):
        replay_portfolio(j,{"USD":D("100")})
    j.close()
