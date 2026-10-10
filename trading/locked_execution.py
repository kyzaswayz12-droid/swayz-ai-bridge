"""Serialised paper-only execution: valuation, risk, fill in one SQLite transaction.

No broker connections. Quotes and FX rates are caller supplied, not independently
authenticated; exchange provenance and durable day-rollover are future gates.
"""
from decimal import Decimal
from .engine import Order, Quote, RiskLimits
from .risk import PortfolioRisk
from .quote_policy import validate_quote_for_paper
from .transactional_ledger import TransactionalPaperLedger, LedgerFill
from .valuation import value_portfolio
from .equity_state import read_equity_state
from .kill_switch import assert_paper_enabled

D = Decimal

def submit_locked(
    ledger: TransactionalPaperLedger, order: Order, *,
    quotes: dict[str, Quote], quote_currency: dict[str, str],
    fx_to_base: dict[str, Decimal], now: float,
    risk: PortfolioRisk = PortfolioRisk(),
    limits: RiskLimits = RiskLimits(),
    fee_rate: Decimal = D("0.001"),
    kill_switch: bool = False,
) -> LedgerFill:
    """Serialise writers using BEGIN IMMEDIATE and roll back all state on failure."""
    if (not order.order_id or order.side not in ("buy", "sell")
        or not order.quantity.is_finite() or order.quantity <= 0
        or not fee_rate.is_finite() or fee_rate < 0):
        raise ValueError("Invalid order")
    instrument = order.instrument
    if (not instrument.symbol or not instrument.quote_currency
        or not instrument.contract_multiplier.is_finite()
        or instrument.contract_multiplier != D("1")):
        raise ValueError("Unsupported instrument")
    if (not limits.max_order_notional.is_finite() or limits.max_order_notional <= 0
        or not limits.max_position_notional.is_finite() or limits.max_position_notional <= 0):
        raise ValueError("Invalid order limits")
    quote = quotes.get(instrument.symbol)
    if quote is None:
        raise ValueError("Missing order quote")
    validate_quote_for_paper(quote, now)
    ledger.conn.execute("BEGIN IMMEDIATE")
    try:
        if ledger.conn.execute("SELECT 1 FROM fills WHERE order_id=?", (order.order_id,)).fetchone():
            raise ValueError("Duplicate order")
        assert_paper_enabled(ledger)
        # The same write transaction protects valuation and subsequent updates.
        for symbol, qty in ledger.conn.execute("SELECT symbol,quantity FROM positions"):
            if D(qty) > 0:
                q = quotes.get(symbol)
                if q is None:
                    raise ValueError("Missing held-position quote")
                validate_quote_for_paper(q, now)
        equity, exposure = value_portfolio(
            ledger, quotes=quotes, quote_currency=quote_currency,
            fx_to_base=fx_to_base)
        day_start, peak = read_equity_state(ledger)
        if not all(v.is_finite() and v > 0 for v in (day_start, peak)):
            raise ValueError("Invalid equity reference state")
        # Compare risk against the previous high-water mark. A new high is
        # recorded only after risk checks succeed and in the same transaction.
        observed_peak = max(peak, equity)
        price = quote.ask if order.side == "buy" else quote.bid
        notional = price * order.quantity
        if notional > limits.max_order_notional:
            raise ValueError("Order notional limit")
        previous = ledger.position(instrument.symbol)
        next_position = previous + (order.quantity if order.side == "buy" else -order.quantity)
        if next_position < 0 or next_position * price > limits.max_position_notional:
            raise ValueError("Position limit")
        fx = fx_to_base.get(instrument.quote_currency)
        if fx is None or not fx.is_finite() or fx <= 0:
            raise ValueError("Missing order FX rate")
        # Sells decrease gross exposure; buys add exposure conservatively.
        proposed = notional * fx if order.side == "buy" else D("0")
        risk.validate(
            starting_equity=day_start, equity=equity,
            peak_equity=peak, gross_exposure=exposure,
            proposed_notional=proposed, kill_switch=kill_switch)
        ledger.conn.execute(
            "UPDATE paper_equity_state SET peak_equity=? WHERE id=1",
            (str(observed_peak),))
        fee = notional * fee_rate
        next_cash = ledger.balance(instrument.quote_currency) + (
            -notional - fee if order.side == "buy" else notional - fee)
        if next_cash < 0:
            raise ValueError("Insufficient cash")
        fill = LedgerFill(order.order_id, instrument.symbol, order.side,
                          order.quantity, price, fee)
        ledger.conn.execute("INSERT INTO fills VALUES(?,?,?,?,?,?)",
            (fill.order_id, fill.symbol, fill.side,
             str(fill.quantity), str(fill.price), str(fill.fee)))
        ledger.conn.execute(
            "INSERT INTO balances(currency,amount) VALUES(?,?) "
            "ON CONFLICT(currency) DO UPDATE SET amount=excluded.amount",
            (instrument.quote_currency, str(next_cash)))
        ledger.conn.execute(
            "INSERT INTO positions(symbol,quantity) VALUES(?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity",
            (instrument.symbol, str(next_position)))
        ledger.conn.execute("COMMIT")
        return fill
    except BaseException:
        ledger.conn.execute("ROLLBACK")
        raise
