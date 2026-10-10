from decimal import Decimal as D
import pytest
from trading.engine import Quote
from trading.quote_policy import validate_quote_for_paper, QuotePolicy

def test_fresh_quote_accepted():
    validate_quote_for_paper(Quote(D("100"),D("100.1"),100),105)

def test_stale_quote_rejected():
    with pytest.raises(ValueError,match="Stale"):
        validate_quote_for_paper(Quote(D("100"),D("100.1"),100),120)

def test_wide_spread_rejected():
    with pytest.raises(ValueError,match="spread"):
        validate_quote_for_paper(Quote(D("90"),D("110"),100),101)

def test_invalid_policy_rejected():
    with pytest.raises(ValueError):
        validate_quote_for_paper(Quote(D("100"),D("101"),100),101,
                                 QuotePolicy(max_spread_fraction=D("NaN")))
