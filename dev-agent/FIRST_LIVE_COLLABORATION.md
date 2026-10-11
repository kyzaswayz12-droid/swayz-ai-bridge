# First live collaboration — execution gate

The one-shot CLI is intentionally **disabled by default**.

Before any real `--execute` run:
1. All tests must pass on Droplet 2.
2. Confirm the emergency-stop database exists and remains stopped.
3. Confirm the budget ledger has capacity for **two $0.50 reservations**.
4. Verify actual provider billing, project-level spending controls and model
   pricing for the exact selected models.
5. Confirm that the selected prompt and token caps fit within the reservation.
   The current reservations are *estimates*, not hard provider-side limits.
6. Ensure the user explicitly authorises this specific paid two-model task.
7. The coordinator may produce a proposal and review only. No source changes,
   GitHub writes, deployment, autonomous service, or live trading.
8. If a provider fails, do not automatically retry; inspect usage and ledger.

The first task is conceptual risk-control test coverage only. The models
cannot claim to have inspected repository files they were not supplied.

The output reports token counts and SHA-256 fingerprints. It must not print
provider secrets. A model's positive review does not equal owner approval.
