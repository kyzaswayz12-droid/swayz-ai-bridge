# Provider dispatch safety status

The `dispatcher.py` module is an offline integration seam, not a production HTTP client.

- Provider dispatch defaults to disabled.
- It validates requests before reserving daily estimated spend.
- Reservations persist on errors, preventing unbounded retries after uncertain billing.
- Provider transport is injected and must not be enabled until HTTPS origin allowlists,
  no redirects, TLS validation, connection/read timeouts and response-size caps exist.
- API keys must come from a protected runtime secret store, never GitHub or Slack.
- The budget ledger tracks estimates; provider-side hard spend controls remain necessary.
- The current dispatcher intentionally does not settle reservations: verified usage-based
  cost accounting and model price schedules need to be implemented first.
- AI outputs are untrusted. Never execute code returned by the provider without a
  separately restricted, resource-limited test worker and approval controls.
- No GitHub writes, production deployments or live trading are permitted.
