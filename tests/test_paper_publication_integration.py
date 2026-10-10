"""End-to-end offline test: paper order -> journal -> public snapshot -> dashboard."""
from decimal import Decimal as D

from trading.engine import Instrument, Market, Order, Quote, PaperAccount
from trading.coordinator import PaperCoordinator
from trading.risk import PortfolioRisk
from trading.journal import PaperJournal
from trading.snapshot import export_public_snapshot
from trading.readonly import ReadOnlyPaperJournal
from trading.dashboard import paper_summary, public_payload
from trading.reconcile import reconcile


def test_private_paper_execution_to_public_dashboard(tmp_path):
    account = PaperAccount()
    journal = PaperJournal()
    coordinator = PaperCoordinator(account, journal, PortfolioRisk())
    instrument = Instrument("BTC/USD", Market.CRYPTO, "USD")

    coordinator.submit(
        Order("research-001", instrument, "buy", D("1")),
        Quote(D("99"), D("100"), 100), 101,
        day_start_equity=D("10000"), current_equity=D("10000"),
        peak_equity=D("10000"), gross_exposure=D("0"),
    )
    assert reconcile(account, journal, {"USD": D("10000")}).consistent

    # Snapshot is a separate sanitised database, not the execution journal.
    snapshot_path = tmp_path / "public.sqlite3"
    assert export_public_snapshot(journal, str(snapshot_path)) == 1
    public_journal = ReadOnlyPaperJournal(str(snapshot_path))
    try:
        result = public_payload(paper_summary(public_journal))
    finally:
        public_journal.close()
        journal.close()

    assert result["mode"] == "PAPER_SIMULATION"
    assert result["fill_count"] == 1
    assert result["performance_verified"] is False
    assert result["instruments"] == ["BTC/USD"]
    assert "balance" not in result
    assert "account_id" not in result
