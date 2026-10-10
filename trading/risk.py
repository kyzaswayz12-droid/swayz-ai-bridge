"""Pure, deterministic portfolio risk guardrails for paper trading."""
from dataclasses import dataclass
from decimal import Decimal

D = Decimal

@dataclass(frozen=True)
class PortfolioRisk:
    max_daily_loss_fraction: Decimal = D("0.02")
    max_drawdown_fraction: Decimal = D("0.10")
    max_gross_exposure_fraction: Decimal = D("0.50")

    def validate(self, *, starting_equity: Decimal, equity: Decimal,
                 peak_equity: Decimal, gross_exposure: Decimal,
                 proposed_notional: Decimal, kill_switch: bool = False) -> None:
        values = (starting_equity, equity, peak_equity, gross_exposure, proposed_notional)
        if not all(v.is_finite() for v in values):
            raise ValueError("Non-finite portfolio value")
        if starting_equity <= 0 or peak_equity <= 0 or equity < 0:
            raise ValueError("Invalid portfolio equity")
        if gross_exposure < 0 or proposed_notional < 0:
            raise ValueError("Negative exposure")
        if kill_switch:
            raise ValueError("Trading disabled by kill switch")
        if starting_equity - equity >= starting_equity * self.max_daily_loss_fraction:
            raise ValueError("Daily loss circuit breaker")
        if peak_equity - equity >= peak_equity * self.max_drawdown_fraction:
            raise ValueError("Drawdown circuit breaker")
        if gross_exposure + proposed_notional > equity * self.max_gross_exposure_fraction:
            raise ValueError("Gross exposure limit")
