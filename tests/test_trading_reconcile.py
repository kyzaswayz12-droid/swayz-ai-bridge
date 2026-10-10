from decimal import Decimal as D
from trading.engine import PaperAccount, Instrument, Market, Order, Quote
from trading.journal import PaperJournal
from trading.risk import PortfolioRisk
from trading.coordinator import PaperCoordinator
from trading.reconcile import reconcile

def test_reconcile_matching_paper_account():
    a=PaperAccount()
    j=PaperJournal()
    c=PaperCoordinator(a,j,PortfolioRisk())
    btc=Instrument("BTC/USD",Market.CRYPTO,"USD")
    c.submit(Order("a",btc,"buy",D("1")),Quote(D("99"),D("100"),10),11,
             day_start_equity=D("10000"),current_equity=D("10000"),
             peak_equity=D("10000"),gross_exposure=D("0"))
    result=reconcile(a,j,{"USD":D("10000")})
    assert result.consistent
    assert result.journal_fill_count==1
    a.balances["USD"]+=D("1")
    changed=reconcile(a,j,{"USD":D("10000")})
    assert not changed.consistent
    assert changed.balance_differences["USD"]=="1"
    j.close()
