"""Clock-checked, operator-authorised paper risk-day rollover wrapper."""
from datetime import datetime,timezone
from decimal import Decimal
from .transactional_ledger import TransactionalPaperLedger
from .engine import Quote
from .risk_day_valuation import rollover_from_ledger

def authorised_rollover(ledger: TransactionalPaperLedger, *,
                        operator_id: str, authorised_operators: frozenset[str],
                        new_day: str, now_utc: datetime,
                        quotes: dict[str,Quote], quote_currency: dict[str,str],
                        fx_to_base: dict[str,Decimal]) -> bool:
    if not operator_id or operator_id not in authorised_operators:
        raise PermissionError("Operator not authorised")
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("Timezone-aware UTC clock required")
    current=now_utc.astimezone(timezone.utc)
    if new_day != current.date().isoformat():
        raise ValueError("Risk rollover day must match current UTC date")
    return rollover_from_ledger(
        ledger,new_day=new_day,quotes=quotes,
        quote_currency=quote_currency,fx_to_base=fx_to_base,
        now=current.timestamp())
