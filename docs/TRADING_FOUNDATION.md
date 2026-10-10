# Swayz AI Trading — first implementation

This branch adds a deliberately isolated **paper-only** execution core.

## Supported primitives
- Crypto, equity, ETF, forex instrument types
- Bid/ask full-fill simulation with configurable percentage fees
- Per-currency cash balances and long-only positions
- Duplicate-order rejection, quote-age checks, notional and position limits
- Deterministic unit tests

## Important limitations
This is not a production trading system. There is **no live market data**, broker connectivity, order routing, persistent ledger, FX conversion, slippage, partial fills, exchange-calendar handling, corporate actions, margin, or portfolio drawdown circuit breaker. The simulator must not be used for real funds.

## Next implementation steps
1. Persist an append-only order/fill ledger and introduce transactional accounting.
2. Add an instrument registry and market-specific trading calendars.
3. Implement market-data adapters and deterministic replay fixtures.
4. Add independent risk checks for daily loss, drawdown, gross exposure and kill switch.
5. Add a capped `team:` orchestration command with ChatGPT proposal and Claude critique, plus explicit approval for any action.
6. Implement sandbox broker adapters, reconciliation and operational monitoring.

Never store broker or AI secrets in this public repository. No real trading keys or withdrawal permissions are required for paper trading.
