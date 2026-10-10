"""Long-only next-bar-open research backtester, paper only.

Uses synthetic bid/ask spreads and fees; no live execution or broker access.
"""
from dataclasses import dataclass
from decimal import Decimal
from .market_data import Candle, validate_candles
from .strategy import moving_average_signals

@dataclass(frozen=True)
class BacktestResult:
    initial_cash: Decimal
    final_equity: Decimal
    total_return_fraction: Decimal
    trades: int
    fees_paid: Decimal
    open_position: Decimal
    mode: str = "PAPER_BACKTEST"

def backtest_crossover(candles: list[Candle], *,
                       initial_cash: Decimal = Decimal("10000"),
                       short_window: int = 5, long_window: int = 20,
                       spread_fraction: Decimal = Decimal("0.001"),
                       fee_fraction: Decimal = Decimal("0.001")) -> BacktestResult:
    if (not initial_cash.is_finite() or initial_cash <= 0
        or not spread_fraction.is_finite() or not (0 <= spread_fraction < 1)
        or not fee_fraction.is_finite() or not (0 <= fee_fraction < 1)):
        raise ValueError("Invalid backtest parameters")
    bars=validate_candles(candles)
    signals=moving_average_signals(bars,short_window=short_window,long_window=long_window)
    signal_by_time={signal.timestamp:signal.signal for signal in signals}
    cash=initial_cash
    quantity=Decimal("0")
    fees=Decimal("0")
    trades=0
    previous_signal="hold"
    half=spread_fraction/2
    for bar in bars:
        # Only the preceding completed bar may generate today's order.
        if previous_signal=="buy_signal" and quantity==0:
            ask=bar.open*(1+half)
            amount=cash/(ask*(1+fee_fraction))
            if amount > 0:
                notional=amount*ask
                fee=notional*fee_fraction
                cash-=notional+fee
                quantity=amount
                fees+=fee
                trades+=1
        elif previous_signal=="sell_signal" and quantity>0:
            bid=bar.open*(1-half)
            notional=quantity*bid
            fee=notional*fee_fraction
            cash+=notional-fee
            quantity=Decimal("0")
            fees+=fee
            trades+=1
        previous_signal=signal_by_time.get(bar.timestamp,"hold")
    final_equity=cash+quantity*bars[-1].close*(1-half) if bars else cash
    return BacktestResult(initial_cash,final_equity,
                          (final_equity-initial_cash)/initial_cash,
                          trades,fees,quantity)
