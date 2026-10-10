from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger,LedgerFill
from trading.valuation import value_portfolio
from trading.engine import Quote

def test_wrong_currency_map_cannot_reprice_position():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("1000"))
    l.execute(LedgerFill("a","BTC/USD","buy",D("1"),D("100"),D("1")),"USD")
    assert l.conn.execute(
        "SELECT quote_currency FROM instrument_registry WHERE symbol='BTC/USD'").fetchone()[0]=="USD"
    with pytest.raises(ValueError,match="currency mismatch"):
        value_portfolio(l,quotes={"BTC/USD":Quote(D("110"),D("111"),100)},
                        quote_currency={"BTC/USD":"EUR"},
                        fx_to_base={"USD":D("1"),"EUR":D("2")})
    assert l.balance("USD")==D("899")
    l.close()

def test_second_fill_cannot_change_instrument_currency():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("1000"))
    l.deposit_opening_cash("EUR",D("1000"))
    l.execute(LedgerFill("a","BTC/USD","buy",D("1"),D("100"),D("0")),"USD")
    with pytest.raises(ValueError,match="currency mismatch"):
        l.execute(LedgerFill("b","BTC/USD","buy",D("1"),D("100"),D("0")),"EUR")
    assert l.position("BTC/USD")==D("1")
    assert l.balance("EUR")==D("1000")
    l.close()
