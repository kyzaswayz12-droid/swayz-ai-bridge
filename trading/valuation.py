"""Trusted paper portfolio valuation from ledger balances and positions.

Requires explicit currency conversion rates and fresh market quotes.
"""
from decimal import Decimal
from .transactional_ledger import TransactionalPaperLedger
from .engine import Quote

D=Decimal

def value_portfolio(ledger: TransactionalPaperLedger, *,
                    quotes: dict[str, Quote],
                    quote_currency: dict[str, str],
                    fx_to_base: dict[str, Decimal],
                    base_currency: str="USD") -> tuple[Decimal,Decimal]:
    """Return (equity, gross_exposure) in base currency.

    Positions marked at bid (conservative long-only liquidation assumption).
    """
    if not base_currency:
        raise ValueError("Missing base currency")
    cash=ledger.conn.execute("SELECT currency,amount FROM balances").fetchall()
    positions=ledger.conn.execute("SELECT symbol,quantity FROM positions").fetchall()
    equity=D("0")
    exposure=D("0")
    for currency,amount in cash:
        rate=fx_to_base.get(currency)
        if rate is None or not rate.is_finite() or rate <= 0:
            raise ValueError("Missing or invalid FX rate")
        value=D(amount)
        if not value.is_finite() or value < 0:
            raise ValueError("Invalid cash balance")
        equity+=value*rate
    for symbol,quantity in positions:
        qty=D(quantity)
        if not qty.is_finite() or qty < 0:
            raise ValueError("Invalid position")
        if qty==0:
            continue
        quote=quotes.get(symbol)
        currency=quote_currency.get(symbol)
        rate=fx_to_base.get(currency) if currency else None
        if (quote is None or not quote.bid.is_finite() or quote.bid <= 0
            or rate is None or not rate.is_finite() or rate <= 0):
            raise ValueError("Missing position quote or FX rate")
        marked=qty*quote.bid*rate
        equity+=marked
        exposure+=marked
    return equity,exposure
