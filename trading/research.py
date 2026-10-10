"""Run a research backtest on validated historical Kraken candles."""
from dataclasses import dataclass
from .market_data import Candle, validate_candles
from .backtest import backtest_crossover, BacktestResult
from .backtest_report import backtest_report

def research_backtest(candles: list[Candle], *,
                      short_window: int=5,long_window: int=20) -> dict:
    bars=validate_candles(candles)
    if len(bars) < long_window+2:
        raise ValueError("Insufficient history for backtest")
    result=backtest_crossover(bars,short_window=short_window,long_window=long_window)
    report=backtest_report(result)
    report["bars_evaluated"]=len(bars)
    report["strategy"]="moving_average_crossover"
    report["data_source_status"]="provided_historical_candles"
    return report
