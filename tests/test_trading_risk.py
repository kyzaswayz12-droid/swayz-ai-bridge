from decimal import Decimal as D
import pytest
from trading.risk import PortfolioRisk

def check(**changes):
    args = dict(starting_equity=D("10000"), equity=D("10000"),
                peak_equity=D("10000"), gross_exposure=D("1000"),
                proposed_notional=D("500"))
    args.update(changes)
    PortfolioRisk().validate(**args)

def test_normal_paper_order():
    check()

@pytest.mark.parametrize("changes", [
    {"equity": D("9800")},
    {"equity": D("8900")},
    {"gross_exposure": D("4800"), "proposed_notional": D("500")},
    {"kill_switch": True},
    {"equity": D("NaN")},
])
def test_risk_rejects(changes):
    with pytest.raises(ValueError):
        check(**changes)
