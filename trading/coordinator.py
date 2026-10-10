"""Paper-only order coordinator; never connects to an exchange."""
from dataclasses import dataclass
from decimal import Decimal
from .engine import PaperAccount, Order, Quote, Fill
from .journal import PaperJournal
from .risk import PortfolioRisk

@dataclass
class PaperCoordinator:
    account: PaperAccount
    journal: PaperJournal
    risk: PortfolioRisk

    def submit(self, order: Order, quote: Quote, now: float,
               *, day_start_equity: Decimal, current_equity: Decimal,
               peak_equity: Decimal, gross_exposure: Decimal,
               kill_switch: bool = False) -> Fill:
        """Fail closed if journal unavailable; record successful paper fills.

        Journal and account are not transactionally coupled yet. On journal failure,
        restore in-memory state and reject; persistence across process crashes is
        a future milestone.
        """
        if order.order_id in self.account.processed_ids:
            raise ValueError("Duplicate order ID")
        price = quote.ask if order.side == "buy" else quote.bid
        proposed = price * order.quantity * order.instrument.contract_multiplier
        self.risk.validate(starting_equity=day_start_equity,
                           equity=current_equity, peak_equity=peak_equity,
                           gross_exposure=gross_exposure,
                           proposed_notional=proposed, kill_switch=kill_switch)
        balances = self.account.balances.copy()
        positions = self.account.positions.copy()
        fills = self.account.fills.copy()
        ids = self.account.processed_ids.copy()
        try:
            fill = self.account.execute(order, quote, now)
            self.journal.append("fill:" + order.order_id, "fill", {
                "symbol": fill.symbol, "side": fill.side, "quantity": fill.quantity,
                "price": fill.price, "fee": fill.fee,
                "quote_currency": order.instrument.quote_currency,
            })
            return fill
        except BaseException:
            self.account.balances = balances
            self.account.positions = positions
            self.account.fills = fills
            self.account.processed_ids = ids
            raise
