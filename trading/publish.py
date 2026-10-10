"""Publication-ready trade updates. No social-network credentials or automatic posting."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

class TradeMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"

@dataclass(frozen=True)
class TradeUpdate:
    trade_id: str
    instrument: str
    market: str
    side: str
    quantity: Decimal
    price: Decimal
    mode: TradeMode
    executed_at_utc: str

def render_trade_update(update: TradeUpdate, *, approved: bool = False) -> str:
    """Generate a factual, explicitly labelled update; require editorial approval."""
    if not approved:
        raise PermissionError("Human publication approval required")
    if update.mode != TradeMode.PAPER:
        raise PermissionError("Live-trade publication disabled in this release")
    if (not update.trade_id or not update.instrument or not update.market
            or not update.executed_at_utc or update.side not in ("buy", "sell")
            or not update.quantity.is_finite() or update.quantity <= 0
            or not update.price.is_finite() or update.price <= 0):
        raise ValueError("Invalid trade update")
    if any("\n" in x or "\r" in x for x in (update.trade_id,update.instrument,update.market,update.executed_at_utc)):
        raise ValueError("Invalid metadata")
    return (
        "PAPER TRADE — SIMULATED, NOT REAL MONEY\n"
        f"ID: {update.trade_id}\n"
        f"Market: {update.market} | Instrument: {update.instrument}\n"
        f"Side: {update.side.upper()} | Quantity: {update.quantity}\n"
        f"Simulated fill price: {update.price}\n"
        f"Recorded (UTC): {update.executed_at_utc}\n"
        "Educational simulation only. Not a recommendation or proof of profitability."
    )
