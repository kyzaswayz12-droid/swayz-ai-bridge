from decimal import Decimal as D
import pytest
from trading.engine import Instrument, Market, Order, Quote, PaperAccount, RiskLimits
from trading.risk import PortfolioRisk

BTC=Instrument("BTC/USD",Market.CRYPTO,"USD")
ORDER=Order("o1",BTC,"buy",D("1"))
QUOTE=Quote(D("99"),D("100"),10)

@pytest.mark.parametrize("balances,positions", [
    ({"USD":D("-1")},{}),
    ({"USD":D("NaN")},{}),
    ({"USD":D("10000")},{"BTC/USD":D("-1")}),
    ({"USD":D("10000")},{"BTC/USD":D("Infinity")}),
])
def test_invalid_account_state_rejected(balances,positions):
    account=PaperAccount(balances=balances,positions=positions)
    with pytest.raises(ValueError):
        account.execute(ORDER,QUOTE,11)
    assert not account.fills

@pytest.mark.parametrize("limit",[
    RiskLimits(max_order_notional=D("NaN")),
    RiskLimits(max_position_notional=D("-1")),
    RiskLimits(max_quote_age_seconds=0),
])
def test_invalid_limits_rejected(limit):
    account=PaperAccount(limits=limit)
    with pytest.raises(ValueError):
        account.execute(ORDER,QUOTE,11)

@pytest.mark.parametrize("limit",[
    PortfolioRisk(max_daily_loss_fraction=D("NaN")),
    PortfolioRisk(max_drawdown_fraction=D("-0.1")),
    PortfolioRisk(max_gross_exposure_fraction=D("2")),
])
def test_invalid_portfolio_risk_config_rejected(limit):
    with pytest.raises(ValueError):
        limit.validate(starting_equity=D("10000"),equity=D("10000"),
                       peak_equity=D("10000"),gross_exposure=D("0"),
                       proposed_notional=D("100"))
