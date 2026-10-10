"""Read-only SQLite paper journal snapshot accessor.

Use only on an immutable, consistent snapshot; never point at a live WAL writer.
"""
import json
import sqlite3
from pathlib import Path

class ReadOnlyPaperJournal:
    def __init__(self, path: str):
        p=Path(path)
        if not p.is_file():
            raise FileNotFoundError("Paper snapshot missing")
        self.conn=sqlite3.connect(p.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)

    def events(self) -> list[dict]:
        rows=self.conn.execute(
            "SELECT sequence,event_id,kind,payload FROM paper_events ORDER BY sequence").fetchall()
        return [{"sequence":seq,"event_id":eid,"kind":kind,"payload":json.loads(payload)}
                for seq,eid,kind,payload in rows]

    def close(self):
        self.conn.close()
