# Paper-trading risk day controls

## Current design
- Paper orders require a persistent enabled kill switch.
- Orders use a locked SQLite transaction for valuation, risk checks and fills.
- High-water-mark observations persist across restarts.
- Daily starting equity is updated only through an explicit rollover operation.
- Ledger-derived rollover calculates equity from cash, positions, market quotes and FX rates.
- The authorised wrapper checks an allowed operator ID and matches the requested date to UTC.

## Important limitations
- Operator IDs are supplied by the caller; there is no cryptographically authenticated identity or role management yet.
- Market quotes and FX conversion rates are supplied by the caller and need trusted provenance and freshness validation.
- The authorised wrapper must be the only exposed rollover entrypoint in a future service.
- The daily reference rollover is not yet a scheduled operation.
- The high-water mark does not replace an independently maintained lifetime maximum drawdown reference or audit log.
- No live-money execution is permitted.

## Before unattended paper trading
1. Enforce authenticated operator identity at the API boundary.
2. Store rollover events in an append-only audit log within the same transaction.
3. Derive UTC date from a trusted server clock inside the service.
4. Add durable price/FX provenance and market-data quality checks.
5. Test concurrent rollover versus order execution and recovery after process termination.
6. Add a daily loss circuit breaker whose state cannot be reset by repeating rollover requests.
