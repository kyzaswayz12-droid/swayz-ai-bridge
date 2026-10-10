from decimal import Decimal as D
from trading.transactional_ledger import TransactionalPaperLedger,LedgerFill
from trading.ledger_snapshot import export_ledger_snapshot
from trading.readonly import ReadOnlyPaperJournal
from trading.dashboard import paper_summary,public_payload

def test_transactional_ledger_is_dashboard_source(tmp_path):
    ledger=TransactionalPaperLedger()
    ledger.deposit_opening_cash("USD",D("1000"))
    ledger.execute(LedgerFill("order-1","BTC/USD","buy",D("1"),D("100"),D("1")),"USD")
    path=str(tmp_path/"public.db")
    assert export_ledger_snapshot(ledger,path)==1
    reader=ReadOnlyPaperJournal(path)
    data=public_payload(paper_summary(reader))
    assert data["fill_count"]==1
    assert data["instruments"]==["BTC/USD"]
    assert data["total_reported_fees"]=="1"
    assert "balance" not in str(data)
    reader.close()
    ledger.close()
