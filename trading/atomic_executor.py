"""Validate and commit paper orders using the transactional ledger.

This module has no broker API or external order capability.
"""
from dataclasses import dataclass
from decimal import Decimal
from .engine import Instrument, Order, Quote, RiskLimits
from .risk import PortfolioRisk
from .quote_policy import validate_quote_for_paper
from .transactional_ledger import TransactionalPaperLedger, LedgerFill

@dataclass
class AtomicPaperExecutor:
    ledger: TransactionalPaperLedger
    portfolio_risk: PortfolioRisk
    order_limits: RiskLimits

    def submit(self, order: Order, quote: Quote, now: float, *,
               day_start_equity: Decimal, equity: Decimal,
               peak_equity: Decimal, gross_exposure: Decimal,
               kill_switch: bool = False,
               fee_rate: Decimal = Decimal("0.001")) -> LedgerFill:
        if (order.side not in ("buy","sell") or not order.quantity.is_finite()
            or order.quantity <= 0 or not fee_rate.is_finite() or fee_rate < 0):
            raise ValueError("Invalid paper order")
        if (not order.instrument.symbol or not order.instrument.quote_currency
            or not order.instrument.contract_multiplier.is_finite()
            or order.instrument.contract_multiplier != 1):
            raise ValueError("Unsupported contract multiplier")
        validate_quote_for_paper(quote,now)
        price=quote.ask if order.side=="buy" else quote.bid
        notional=price*order.quantity
        if notional > self.order_limits.max_order_notional:
            raise ValueError("Order limit exceeded")
        position=self.ledger.position(order.instrument.symbol)
        next_qty=position+(order.quantity if order.side=="buy" else -order.quantity)
        if next_qty < 0 or next_qty*price > self.order_limits.max_position_notional:
            raise ValueError("Position limit exceeded")
        self.portfolio_risk.validate(
            starting_equity=day_start_equity,equity=equity,
            peak_equity=peak_equity,gross_exposure=gross_exposure,
            proposed_notional=notional if order.side=="buy" else Decimal("0"),
            kill_switch=kill_switch)
        fill=LedgerFill(order.order_id,order.instrument.symbol,order.side,
                        order.quantity,price,notional*fee_rate)
        self.ledger.execute(fill,order.instrument.quote_currency)
        return fill
