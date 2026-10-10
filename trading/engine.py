"""Deterministic, paper-only multi-market order simulator."""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List

D = Decimal

class Market(str, Enum):
    CRYPTO = "crypto"
    EQUITY = "equity"
    ETF = "etf"
    FOREX = "forex"

@dataclass(frozen=True)
class Instrument:
    symbol: str
    market: Market
    quote_currency: str
    contract_multiplier: Decimal = D("1")

@dataclass(frozen=True)
class Order:
    order_id: str
    instrument: Instrument
    side: str
    quantity: Decimal

@dataclass(frozen=True)
class Quote:
    bid: Decimal
    ask: Decimal
    timestamp: float

@dataclass(frozen=True)
class RiskLimits:
    max_order_notional: Decimal = D("1000")
    max_position_notional: Decimal = D("2000")
    max_quote_age_seconds: float = 30

@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal

@dataclass
class PaperAccount:
    balances: Dict[str, Decimal] = field(default_factory=lambda: {"USD": D("10000")})
    positions: Dict[str, Decimal] = field(default_factory=dict)
    fills: List[Fill] = field(default_factory=list)
    processed_ids: set = field(default_factory=set)
    limits: RiskLimits = field(default_factory=RiskLimits)

    def execute(self, order: Order, quote: Quote, now: float, fee_rate: Decimal = D("0.001")) -> Fill:
        """Execute a full simulated fill at bid/ask; no network or live execution."""
        if not order.order_id or order.order_id in self.processed_ids:
            raise ValueError("Missing or duplicate order ID")
        if order.side not in ("buy", "sell") or not order.quantity.is_finite() or order.quantity <= 0:
            raise ValueError("Invalid order")
        if not (quote.bid.is_finite() and quote.ask.is_finite() and D("0") < quote.bid <= quote.ask):
            raise ValueError("Invalid quote")
        if now < quote.timestamp or now - quote.timestamp > self.limits.max_quote_age_seconds:
            raise ValueError("Stale or future quote")
        if not fee_rate.is_finite() or fee_rate < 0:
            raise ValueError("Invalid fee")
        instrument = order.instrument
        if not instrument.symbol or not instrument.quote_currency or not instrument.contract_multiplier.is_finite() or instrument.contract_multiplier <= 0:
            raise ValueError("Invalid instrument")
        price = quote.ask if order.side == "buy" else quote.bid
        notional = price * order.quantity * instrument.contract_multiplier
        if notional > self.limits.max_order_notional:
            raise ValueError("Order notional limit exceeded")
        previous = self.positions.get(instrument.symbol, D("0"))
        next_qty = previous + (order.quantity if order.side == "buy" else -order.quantity)
        if next_qty < 0:
            raise ValueError("Short selling disabled")
        if abs(next_qty) * price * instrument.contract_multiplier > self.limits.max_position_notional:
            raise ValueError("Position limit exceeded")
        fee = notional * fee_rate
        currency = instrument.quote_currency
        balance = self.balances.get(currency, D("0"))
        new_balance = balance - notional - fee if order.side == "buy" else balance + notional - fee
        if new_balance < 0:
            raise ValueError("Insufficient quote-currency balance")
        fill = Fill(order.order_id, instrument.symbol, order.side, order.quantity, price, fee)
        self.balances[currency] = new_balance
        self.positions[instrument.symbol] = next_qty
        self.fills.append(fill)
        self.processed_ids.add(order.order_id)
        return fill
