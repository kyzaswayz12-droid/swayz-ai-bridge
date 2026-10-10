# Reproducible historical strategy research

## Purpose
Every research run should identify:
- Market pair and candle interval
- Exact dataset fingerprint
- First and last completed candle timestamps
- Strategy parameters
- Simulated execution assumptions and trading costs
- Research report and simulation disclosure

## Data integrity
Use completed, chronological candles. Reject gaps, duplicates, malformed prices and invalid volume. Preserve original downloaded responses separately from transformed research datasets.

## Limitations
A SHA-256 fingerprint identifies the dataset bytes after canonicalisation; it does not authenticate the exchange or establish that historical records are correct.

The first moving-average backtester assumes next-bar open execution, synthetic spreads, fixed percentage fees, full fills and no liquidity constraints. It does not model financing, taxes, exchange outages, market impact or corporate actions. Do not treat results as verified profitability.

## Next milestones
1. Run one controlled public historical-data import.
2. Store the raw response and validated candles with provenance metadata.
3. Add out-of-sample train/test partitioning and benchmark comparison.
4. Add equity-curve drawdown, trade ledger and risk-adjusted performance statistics.
5. Ask ChatGPT and Claude to review the same research manifest independently.
