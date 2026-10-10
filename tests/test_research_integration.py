"""End-to-end offline test: Kraken payload -> completed candles -> research report.

This exercises the real modules together, with no HTTP or trading account.
"""
import asyncio
from decimal import Decimal
from trading.historical_fetch import fetch_kraken_ohlc
from trading.research_manifest import research_manifest
from trading.dataset_fingerprint import candle_fingerprint

class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        # 32 closed hourly bars followed by an unfinished bar.
        prices = [100 - i for i in range(12)] + [88 + i for i in range(21)]
        rows = [
            [3600 * (i + 1), str(p), str(p), str(p), str(p), str(p), "10", 1]
            for i, p in enumerate(prices)
        ]
        return {"error": [], "result": {"XXBTZUSD": rows, "last": 0}}

class FakeClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()

def test_historical_research_pipeline_is_causal_and_reproducible():
    client = FakeClient()
    # 32 bars completed, final (33rd) bar still forming.
    bars = asyncio.run(fetch_kraken_ohlc(
        client, pair="XBTUSD", interval=60, observed_at=33 * 3600 + 100))
    assert len(bars) == 32
    assert len(client.calls) == 1
    assert client.calls[0][0].endswith("/0/public/OHLC")
    report = research_manifest(
        bars, pair="XBTUSD", interval_minutes=60,
        short_window=3, long_window=8)
    assert report["report"]["mode"] == "PAPER_BACKTEST"
    assert report["report"]["verified_live_performance"] is False
    assert report["dataset_sha256"] == candle_fingerprint(bars)
    assert report == research_manifest(
        bars, pair="XBTUSD", interval_minutes=60,
        short_window=3, long_window=8)
    assert Decimal(report["report"]["simulated_fees"]) >= 0
    assert report["report"]["bars_evaluated"] == 32
