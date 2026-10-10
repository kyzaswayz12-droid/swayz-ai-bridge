"""Export a consistent, sanitised paper-trade snapshot for the public dashboard."""
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from .journal import PaperJournal

PUBLIC_FILL_FIELDS = ("symbol", "side", "quantity", "price", "fee", "quote_currency")

def export_public_snapshot(source: PaperJournal, destination: str) -> int:
    """Export only paper fill fields to a separate SQLite database.

    Caller must provide a destination distinct from the source journal.
    This function does not publish the snapshot or change any trading state.
    """
    target=Path(destination)
    if target.exists():
        raise FileExistsError("Refusing to overwrite an existing snapshot")
    target.parent.mkdir(parents=True,exist_ok=True)
    events=source.events()
    fd,tmp=tempfile.mkstemp(prefix=".paper-snapshot-",suffix=".db",dir=str(target.parent))
    os.close(fd)
    conn=None
    try:
        conn=sqlite3.connect(tmp)
        conn.execute("""CREATE TABLE paper_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at REAL NOT NULL
        )""")
        count=0
        with conn:
            for event in events:
                if event["kind"]!="fill":
                    continue
                payload=event["payload"]
                filtered={field:payload[field] for field in PUBLIC_FILL_FIELDS if field in payload}
                conn.execute(
                    "INSERT INTO paper_events(event_id,kind,payload,created_at) VALUES(?,?,?,?)",
                    (event["event_id"],"fill",json.dumps(filtered,sort_keys=True),0.0))
                count+=1
        conn.close()
        conn=None
        os.chmod(tmp,0o644)
        os.link(tmp,target)
        return count
    finally:
        if conn is not None:
            conn.close()
        if os.path.exists(tmp):
            os.unlink(tmp)
