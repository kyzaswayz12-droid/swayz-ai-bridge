# Swayz Trading — subscriber distribution architecture

## Channels
- **Slack:** owner-only operations and approvals
- **Telegram:** subscriber announcements via a bot added as channel administrator
- **Discord:** subscriber updates through a restricted channel webhook or bot
- **X / YouTube:** later-stage editorial distribution, not order routing

## Publication lifecycle
1. Create a draft from a verified paper fill.
2. Label it unambiguously as **PAPER TRADE — SIMULATED, NOT REAL MONEY**.
3. Review factual accuracy, timestamps, prices, market, fees and performance claims.
4. Require a designated owner approval.
5. Record the approved publication in a durable outbox.
6. Claim for delivery; log provider response and external message ID.
7. Mark sent only after an acknowledged provider response.
8. Reconcile uncertain outcomes manually rather than blindly retrying.

## Security requirements
- Store API tokens and webhook URLs in a secret manager or protected server environment, never GitHub.
- Only the publisher service may access social posting credentials; it has no broker order privileges.
- Use separate platform-specific rate limits, destinations and permission scopes.
- Never publish customer identities, account balances, API keys or unpublished strategies.
- Never auto-publish an AI-generated claim without source verification and explicit owner approval.

## Regulatory and editorial review
Before commercial UK launch, obtain appropriate legal/compliance advice on financial promotions, investment recommendations, paid signals, performance advertising and any regulated activities. Simulation labels alone do not establish compliance. Show verified losses as well as wins, and avoid selective performance presentation.

## Not implemented yet
Actual Telegram and Discord network delivery, subscriber entitlements, billing, privacy policies, retention, provider idempotency and external delivery reconciliation.
