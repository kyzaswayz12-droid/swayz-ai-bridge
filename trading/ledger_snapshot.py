"""Export public dashboard snapshots directly from transactional paper fills.

No dependency on the legacy mutable PaperJournal execution path.
"""
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from .transactional_ledger import TransactionalPaperLedger

def export_ledger_snapshot(ledger: TransactionalPaperLedger, destination: str) -> int:
    target=Path(destination)
    if target.exists():
        raise FileExistsError("Refusing to overwrite snapshot")
    target.parent.mkdir(parents=True,exist_ok=True)
    # Single SQLite read transaction gives one coherent set of fills.
    ledger.conn.execute("BEGIN")
    try:
        rows=ledger.conn.execute(
            "SELECT order_id,symbol,side,quantity,price,fee FROM fills ORDER BY rowid").fetchall()
        ledger.conn.execute("COMMIT")
    except BaseException:
        ledger.conn.execute("ROLLBACK")
        raise
    fd,tmp=tempfile.mkstemp(prefix=".ledger-public-",suffix=".db",dir=str(target.parent))
    os.close(fd)
    conn=None
    try:
        conn=sqlite3.connect(tmp)
        conn.execute("""CREATE TABLE paper_events(
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at REAL NOT NULL
        )""")
        with conn:
            for order_id,symbol,side,quantity,price,fee in rows:
                payload={"symbol":symbol,"side":side,"quantity":quantity,
                         "price":price,"fee":fee}
                conn.execute(
                    "INSERT INTO paper_events(event_id,kind,payload,created_at) VALUES(?,?,?,0)",
                    (order_id,"fill",json.dumps(payload,sort_keys=True)))
        conn.close()
        conn=None
        os.chmod(tmp,0o644)
        os.link(tmp,target)
        return len(rows)
    finally:
        if conn is not None:
            conn.close()
        if os.path.exists(tmp):
            os.unlink(tmp)
