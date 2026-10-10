from datetime import datetime,timezone
from decimal import Decimal as D
import pytest
from trading.transactional_ledger import TransactionalPaperLedger
from trading.risk_day_authorisation import authorised_rollover

def test_unauthorised_operator_rejected():
    ledger=TransactionalPaperLedger()
    with pytest.raises(PermissionError):
        authorised_rollover(ledger,operator_id="guest",
            authorised_operators=frozenset({"owner"}),
            new_day="2026-10-10",
            now_utc=datetime(2026,10,10,tzinfo=timezone.utc),
            quotes={},quote_currency={},fx_to_base={"USD":D("1")})
    ledger.close()

def test_wrong_utc_date_rejected():
    ledger=TransactionalPaperLedger()
    with pytest.raises(ValueError,match="current UTC"):
        authorised_rollover(ledger,operator_id="owner",
            authorised_operators=frozenset({"owner"}),
            new_day="2026-10-09",
            now_utc=datetime(2026,10,10,tzinfo=timezone.utc),
            quotes={},quote_currency={},fx_to_base={"USD":D("1")})
    ledger.close()
