from decimal import Decimal as D
from trading.backtest import BacktestResult
from trading.backtest_report import backtest_report

def test_report_discloses_simulation():
    result=BacktestResult(D("1000"),D("990"),D("-0.01"),2,D("3"),D("0"))
    report=backtest_report(result)
    assert report["mode"]=="PAPER_BACKTEST"
    assert report["verified_live_performance"] is False
    assert report["simulated_return_fraction"]=="-0.01"
    assert "Historical simulation" in report["disclosure"]
