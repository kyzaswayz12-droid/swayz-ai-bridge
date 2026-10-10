from decimal import Decimal as D
import pytest
from trading.engine import Instrument, Market, Order, Quote, RiskLimits
from trading.risk import PortfolioRisk
from trading.transactional_ledger import TransactionalPaperLedger
from trading.atomic_executor import AtomicPaperExecutor

BTC=Instrument("BTC/USD",Market.CRYPTO,"USD")

def submit(executor,*,kill_switch=False):
    return executor.submit(
        Order("order1",BTC,"buy",D("1")),
        Quote(D("99"),D("100"),100),101,
        day_start_equity=D("1000"),equity=D("1000"),
        peak_equity=D("1000"),gross_exposure=D("0"),
        kill_switch=kill_switch)

def test_atomic_paper_order_flow():
    ledger=TransactionalPaperLedger()
    ledger.deposit_opening_cash("USD",D("1000"))
    executor=AtomicPaperExecutor(ledger,PortfolioRisk(),RiskLimits())
    fill=submit(executor)
    assert fill.price==D("100")
    assert ledger.balance("USD")==D("899.900")
    assert ledger.position("BTC/USD")==D("1")
    ledger.close()

def test_kill_switch_prevents_commit():
    ledger=TransactionalPaperLedger()
    ledger.deposit_opening_cash("USD",D("1000"))
    executor=AtomicPaperExecutor(ledger,PortfolioRisk(),RiskLimits())
    with pytest.raises(ValueError,match="kill switch"):
        submit(executor,kill_switch=True)
    assert ledger.balance("USD")==D("1000")
    assert ledger.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]==0
    ledger.close()
