"""Reconstruct a long-only paper portfolio from append-only journal events.

Replay is a diagnostic projection, not yet a transactionally guaranteed ledger.
"""
from dataclasses import dataclass
from decimal import Decimal
from .journal import PaperJournal

@dataclass(frozen=True)
class ReplayedPortfolio:
    balances: dict[str, Decimal]
    positions: dict[str, Decimal]
    fill_count: int

def replay_portfolio(journal: PaperJournal, opening_balances: dict[str, Decimal]) -> ReplayedPortfolio:
    balances=dict(opening_balances)
    positions: dict[str, Decimal]={}
    for currency, balance in balances.items():
        if not currency or not balance.is_finite() or balance < 0:
            raise ValueError("Invalid opening balance")
    count=0
    for event in journal.events():
        if event["kind"] != "fill":
            continue
        p=event["payload"]
        try:
            symbol=str(p["symbol"])
            currency=str(p["quote_currency"])
            side=str(p["side"])
            quantity=Decimal(str(p["quantity"]))
            price=Decimal(str(p["price"]))
            fee=Decimal(str(p["fee"]))
        except (KeyError, ValueError, ArithmeticError) as exc:
            raise ValueError("Malformed journal fill") from exc
        if (not symbol or not currency or side not in ("buy","sell")
            or not all(v.is_finite() for v in (quantity,price,fee))
            or quantity <= 0 or price <= 0 or fee < 0):
            raise ValueError("Invalid journal fill")
        notional=quantity*price
        previous=positions.get(symbol,Decimal("0"))
        next_qty=previous+(quantity if side=="buy" else -quantity)
        next_balance=balances.get(currency,Decimal("0"))+(
            -notional-fee if side=="buy" else notional-fee)
        if next_qty < 0 or next_balance < 0:
            raise ValueError("Journal violates long-only or cash constraints")
        positions[symbol]=next_qty
        balances[currency]=next_balance
        count+=1
    return ReplayedPortfolio(balances,positions,count)
