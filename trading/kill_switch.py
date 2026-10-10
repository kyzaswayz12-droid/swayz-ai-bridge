"""Persistent, fail-closed kill switch for paper execution."""
from .transactional_ledger import TransactionalPaperLedger

def initialise_kill_switch(ledger: TransactionalPaperLedger, *, stopped: bool = True) -> None:
    ledger.conn.execute("""CREATE TABLE IF NOT EXISTS paper_control(
        id INTEGER PRIMARY KEY CHECK(id=1),
        stopped INTEGER NOT NULL CHECK(stopped IN (0,1))
    )""")
    ledger.conn.execute(
        "INSERT OR IGNORE INTO paper_control(id,stopped) VALUES(1,?)",
        (int(stopped),))

def set_kill_switch(ledger: TransactionalPaperLedger, stopped: bool) -> None:
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        result=ledger.conn.execute(
            "UPDATE paper_control SET stopped=? WHERE id=1",(int(stopped),))
        if result.rowcount!=1:
            raise ValueError("Paper control state missing")
        ledger.conn.execute("COMMIT")
    except BaseException:
        ledger.conn.execute("ROLLBACK")
        raise

def assert_paper_enabled(ledger: TransactionalPaperLedger) -> None:
    try:
        row=ledger.conn.execute("SELECT stopped FROM paper_control WHERE id=1").fetchone()
    except __import__("sqlite3").OperationalError as exc:
        raise ValueError("Paper control state missing") from exc
    if not row or row[0]!=0:
        raise ValueError("Paper trading disabled by persistent kill switch")
