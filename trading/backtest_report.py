"""Summarise paper backtest results without presenting them as verified returns."""
from dataclasses import asdict
from .backtest import BacktestResult

def backtest_report(result: BacktestResult) -> dict:
    return {
        "mode": result.mode,
        "initial_cash": str(result.initial_cash),
        "final_equity": str(result.final_equity),
        "simulated_return_fraction": str(result.total_return_fraction),
        "simulated_trades": result.trades,
        "simulated_fees": str(result.fees_paid),
        "open_position": str(result.open_position),
        "verified_live_performance": False,
        "disclosure": (
            "Historical simulation only. Synthetic spreads and fees; no "
            "guarantee of executable prices or future returns."
        ),
    }
