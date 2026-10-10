from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger,LedgerFill
from trading.engine import Quote
from trading.valuation import value_portfolio

def test_portfolio_equity_from_ledger():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("1000"))
    l.execute(LedgerFill("1","BTC/USD","buy",D("1"),D("100"),D("1")),"USD")
    equity,exposure=value_portfolio(l,quotes={"BTC/USD":Quote(D("110"),D("111"),100)},
                                    quote_currency={"BTC/USD":"USD"},fx_to_base={"USD":D("1")})
    assert equity==D("1009")
    assert exposure==D("110")
    l.close()

def test_missing_quote_fails_closed():
    l=TransactionalPaperLedger()
    l.deposit_opening_cash("USD",D("1000"))
    l.execute(LedgerFill("1","BTC/USD","buy",D("1"),D("100"),D("1")),"USD")
    with pytest.raises(ValueError):
        value_portfolio(l,quotes={},quote_currency={"BTC/USD":"USD"},fx_to_base={"USD":D("1")})
    l.close()
