# Manual public Kraken smoke test

This test is intentionally manual and performs one read-only request to Kraken's public ticker endpoint. It uses no trading API key and places no orders.

## Running from GitHub
1. Open GitHub Actions and locate **Kraken public quote smoke test**.
2. Choose **Run workflow** and select the development branch if GitHub offers it.
3. Review the run output for a valid quote and no API errors.
4. Do not run it repeatedly; it is a connectivity smoke test, not a collector schedule.

## Acceptance criteria
- Public endpoint reachable.
- Bid and ask positive, finite and correctly ordered.
- Quote passes freshness/spread policy at observation time.
- No secrets, private account data or order endpoints used.

## Limitations
- An observation timestamp assigned on receipt is not the exchange's trade timestamp.
- Public bid/ask data is not proof of executable fill or available depth.
- UK access restrictions, broker eligibility and production market-data licensing require separate checks.
- This workflow is not automatically scheduled or dispatched.
