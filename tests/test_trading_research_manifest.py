from decimal import Decimal as D
from trading.market_data import Candle
from trading.research_manifest import research_manifest

def test_manifest_records_data_and_parameters():
    bars=[Candle(float(i),D("10"),D("10"),D("10"),D("10"),D("1"))
          for i in range(1,30)]
    report=research_manifest(bars,pair="XBTUSD",interval_minutes=60,
                             short_window=2,long_window=4)
    assert len(report["dataset_sha256"])==64
    assert report["strategy_parameters"]["short_window"]==2
    assert report["report"]["verified_live_performance"] is False
    assert report["source_verification"]=="not independently verified"
