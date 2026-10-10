# Read-only Kraken collector staging

## Safety
- Public ticker only: XBTUSD and ETHUSD. No Kraken private API key required.
- Minimum 60 seconds between collection attempts per controller.
- Stop after 3 consecutive failures; manual review required.
- Bounded SQLite quote archive, currently default 10,000 rows.
- One-shot collector calls only; no unattended service has been deployed.

## Proposed validation
1. Run unit tests with mocked HTTP responses.
2. Verify public ticker API documentation, symbol aliases and permitted polling rates.
3. Use an isolated container with outbound HTTPS only and no broker/Slack secrets.
4. Capture one real quote, record observed timestamp and compare to exchange response.
5. Test timeouts, API errors, invalid prices, stale quotes and rate-limit responses.
6. Add metrics, clock synchronisation, durable circuit-breaker state and scheduling before continuous polling.

## Limitations
Ticker prices are indicative. A public quote is not proof of executable liquidity, fees, fills or a profitable strategy. Collector rate-limits and circuit-breaker state are currently in-memory and reset on restart. Do not use these quotes to place real orders.
