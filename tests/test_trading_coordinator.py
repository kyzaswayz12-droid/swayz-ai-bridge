from decimal import Decimal as D
import pytest
from trading.engine import Instrument, Market, Order, Quote, PaperAccount
from trading.journal import PaperJournal
from trading.risk import PortfolioRisk
from trading.coordinator import PaperCoordinator

BTC = Instrument("BTC/USD", Market.CRYPTO, "USD")
def make():
    return PaperCoordinator(PaperAccount(), PaperJournal(), PortfolioRisk())

def submit(c, **kw):
    args = dict(day_start_equity=D("10000"), current_equity=D("10000"),
                peak_equity=D("10000"), gross_exposure=D("0"))
    args.update(kw)
    return c.submit(Order("buy1", BTC, "buy", D("1")),
                    Quote(D("99"), D("100"), 10), 11, **args)

def test_fill_is_journaled():
    c = make()
    fill = submit(c)
    assert fill.price == D("100")
    assert c.journal.events()[0]["event_id"] == "fill:buy1"
    assert c.account.positions["BTC/USD"] == D("1")

def test_kill_switch_rejects_without_mutation():
    c = make()
    with pytest.raises(ValueError, match="kill switch"):
        submit(c, kill_switch=True)
    assert not c.journal.events()
    assert not c.account.fills

def test_journal_failure_restores_account():
    c = make()
    c.journal.close()
    with pytest.raises(Exception):
        submit(c)
    assert c.account.balances["USD"] == D("10000")
    assert not c.account.positions
    assert not c.account.processed_ids
