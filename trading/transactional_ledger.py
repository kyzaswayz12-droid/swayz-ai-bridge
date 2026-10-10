"""Transactional, long-only paper cash and position ledger.

SQLite atomicity covers one order and its resulting state. No live broker access.
"""
import sqlite3
from dataclasses import dataclass
from decimal import Decimal

D=Decimal

@dataclass(frozen=True)
class LedgerFill:
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal

class TransactionalPaperLedger:
    def __init__(self,path: str = ":memory:"):
        self.conn=sqlite3.connect(path,isolation_level=None)
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS balances (
            currency TEXT PRIMARY KEY, amount TEXT NOT NULL)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY, quantity TEXT NOT NULL)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS instrument_registry (
            symbol TEXT PRIMARY KEY, quote_currency TEXT NOT NULL)""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS fills (
            order_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL,
            quantity TEXT NOT NULL, price TEXT NOT NULL, fee TEXT NOT NULL)""")

    def deposit_opening_cash(self,currency: str,amount: Decimal) -> None:
        if not currency or not amount.is_finite() or amount <= 0:
            raise ValueError("Invalid opening cash")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if self.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]:
                raise ValueError("Cannot initialise cash after trading")
            if self.conn.execute("SELECT 1 FROM balances WHERE currency=?",(currency,)).fetchone():
                raise ValueError("Opening balance already set")
            self.conn.execute("INSERT INTO balances VALUES(?,?)",(currency,str(amount)))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def balance(self,currency: str) -> Decimal:
        row=self.conn.execute("SELECT amount FROM balances WHERE currency=?",(currency,)).fetchone()
        return D(row[0]) if row else D("0")

    def position(self,symbol: str) -> Decimal:
        row=self.conn.execute("SELECT quantity FROM positions WHERE symbol=?",(symbol,)).fetchone()
        return D(row[0]) if row else D("0")

    def execute(self,fill: LedgerFill,currency: str) -> None:
        if (not fill.order_id or not fill.symbol or not currency or
            fill.side not in ("buy","sell") or
            not all(x.is_finite() for x in (fill.quantity,fill.price,fill.fee)) or
            fill.quantity <= 0 or fill.price <= 0 or fill.fee < 0):
            raise ValueError("Invalid paper fill")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if self.conn.execute("SELECT 1 FROM fills WHERE order_id=?",(fill.order_id,)).fetchone():
                raise ValueError("Duplicate order")
            registered=self.conn.execute(
                "SELECT quote_currency FROM instrument_registry WHERE symbol=?",
                (fill.symbol,)).fetchone()
            if registered and registered[0] != currency:
                raise ValueError("Instrument currency mismatch")
            if not registered:
                # Existing holdings without a registry record are ambiguous:
                # refuse migration instead of guessing their currency.
                if self.position(fill.symbol) != 0:
                    raise ValueError("Existing position missing registered currency")
                self.conn.execute(
                    "INSERT INTO instrument_registry(symbol,quote_currency) VALUES(?,?)",
                    (fill.symbol,currency))
            cash=self.balance(currency)
            position=self.position(fill.symbol)
            notional=fill.quantity*fill.price
            next_position=position+(fill.quantity if fill.side=="buy" else -fill.quantity)
            next_cash=cash+(-notional-fill.fee if fill.side=="buy" else notional-fill.fee)
            if next_position < 0 or next_cash < 0:
                raise ValueError("Insufficient cash or long position")
            self.conn.execute(
                "INSERT INTO fills VALUES(?,?,?,?,?,?)",
                (fill.order_id,fill.symbol,fill.side,str(fill.quantity),str(fill.price),str(fill.fee)))
            self.conn.execute(
                "INSERT INTO balances(currency,amount) VALUES(?,?) "
                "ON CONFLICT(currency) DO UPDATE SET amount=excluded.amount",
                (currency,str(next_cash)))
            self.conn.execute(
                "INSERT INTO positions(symbol,quantity) VALUES(?,?) "
                "ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity",
                (fill.symbol,str(next_position)))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def close(self):
        self.conn.close()
