"""Bounded SQLite archive for observed public market quotes."""
import sqlite3
from decimal import Decimal
from .engine import Quote
from .quote_policy import validate_quote_for_paper, QuotePolicy

class QuoteArchive:
    def __init__(self, path: str = ":memory:", max_rows: int = 10000):
        if max_rows < 1:
            raise ValueError("Invalid archive capacity")
        self.conn=sqlite3.connect(path)
        self.max_rows=max_rows
        with self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS market_quotes(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                pair TEXT NOT NULL,
                observed_at REAL NOT NULL,
                bid TEXT NOT NULL,
                ask TEXT NOT NULL
            )""")

    def record(self, source: str, pair: str, quote: Quote, now: float) -> int:
        if source not in ("kraken",) or pair not in ("XBTUSD","ETHUSD"):
            raise ValueError("Unsupported source or pair")
        validate_quote_for_paper(quote,now,QuotePolicy())
        with self.conn:
            cursor=self.conn.execute(
                "INSERT INTO market_quotes(source,pair,observed_at,bid,ask) VALUES(?,?,?,?,?)",
                (source,pair,quote.timestamp,str(quote.bid),str(quote.ask)))
            self.conn.execute(
                "DELETE FROM market_quotes WHERE id IN "
                "(SELECT id FROM market_quotes ORDER BY id DESC LIMIT -1 OFFSET ?)",
                (self.max_rows,))
            return int(cursor.lastrowid)

    def recent(self, pair: str, limit: int = 100) -> list[dict]:
        if pair not in ("XBTUSD","ETHUSD") or not (1 <= limit <= 1000):
            raise ValueError("Invalid query")
        rows=self.conn.execute(
            "SELECT source,observed_at,bid,ask FROM market_quotes "
            "WHERE pair=? ORDER BY id DESC LIMIT ?",(pair,limit)).fetchall()
        return [{"source":source,"observed_at":ts,"bid":Decimal(bid),"ask":Decimal(ask)}
                for source,ts,bid,ask in rows]

    def close(self):
        self.conn.close()
