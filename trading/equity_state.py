"""Persistent paper equity reference points for risk evaluation."""
import sqlite3
from decimal import Decimal
from .transactional_ledger import TransactionalPaperLedger

D=Decimal

def ensure_equity_state(ledger: TransactionalPaperLedger, initial_equity: Decimal) -> None:
    if not initial_equity.is_finite() or initial_equity <= 0:
        raise ValueError("Invalid initial equity")
    ledger.conn.execute("""CREATE TABLE IF NOT EXISTS paper_equity_state(
        id INTEGER PRIMARY KEY CHECK(id=1),
        day_start_equity TEXT NOT NULL,
        peak_equity TEXT NOT NULL
    )""")
    ledger.conn.execute(
        "INSERT OR IGNORE INTO paper_equity_state(id,day_start_equity,peak_equity) VALUES(1,?,?)",
        (str(initial_equity),str(initial_equity)))

def read_equity_state(ledger: TransactionalPaperLedger) -> tuple[Decimal,Decimal]:
    try:
        row=ledger.conn.execute(
            "SELECT day_start_equity,peak_equity FROM paper_equity_state WHERE id=1").fetchone()
    except sqlite3.OperationalError as exc:
        raise ValueError("Paper equity reference state missing") from exc
    if not row:
        raise ValueError("Paper equity reference state missing")
    return D(row[0]),D(row[1])
