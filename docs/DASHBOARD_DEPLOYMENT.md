# Standalone paper dashboard deployment — review checklist

**Not yet approved for production.** No live broker connectivity.

## Build
```bash
docker build -f Dockerfile.dashboard -t swayz-paper-dashboard:review .
```

## Safe initial test
- Run only on loopback, not a public port.
- Mount a dedicated **copy** of a paper journal, not the live Slack bridge database.
- Do not pass OpenAI, Anthropic, Slack, broker, Telegram or Discord credentials.
- Verify `/health`, `/`, and `/api/paper-summary`.
- Confirm `POST /api/orders` returns 404.
- Confirm dashboard data includes simulation disclosure and no private identifiers.
- Confirm no outbound network requests are required to render the page.

## Security gates before public access
- Independent reverse proxy, TLS, authentication if needed, rate limiting and access logs.
- Decide whether journal data is public and minimise metadata exposure.
- Use a read-only data snapshot or a separate projection database, not direct write access to the trading ledger.
- Add retention, backup, error monitoring, deployment rollback and secret scanning.
- Regulatory and legal review before promoting paid trade signals or financial products.

Do not merge or deploy solely because unit tests pass.
