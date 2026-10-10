"""Compare current paper account state to an independently replayed journal.

A mismatch must halt paper execution; this module does not repair state.
"""
from dataclasses import dataclass
from decimal import Decimal
from .engine import PaperAccount
from .journal import PaperJournal
from .replay import replay_portfolio

@dataclass(frozen=True)
class Reconciliation:
    consistent: bool
    balance_differences: dict[str, str]
    position_differences: dict[str, str]
    journal_fill_count: int

def reconcile(account: PaperAccount, journal: PaperJournal,
              opening_balances: dict[str, Decimal]) -> Reconciliation:
    replayed=replay_portfolio(journal,opening_balances)
    balance_keys=set(account.balances)|set(replayed.balances)
    position_keys=set(account.positions)|set(replayed.positions)
    balance_differences={
        currency: str(account.balances.get(currency,Decimal("0")) -
                      replayed.balances.get(currency,Decimal("0")))
        for currency in sorted(balance_keys)
        if account.balances.get(currency,Decimal("0")) !=
           replayed.balances.get(currency,Decimal("0"))
    }
    position_differences={
        symbol: str(account.positions.get(symbol,Decimal("0")) -
                    replayed.positions.get(symbol,Decimal("0")))
        for symbol in sorted(position_keys)
        if account.positions.get(symbol,Decimal("0")) !=
           replayed.positions.get(symbol,Decimal("0"))
    }
    return Reconciliation(not balance_differences and not position_differences,
                          balance_differences,position_differences,replayed.fill_count)
