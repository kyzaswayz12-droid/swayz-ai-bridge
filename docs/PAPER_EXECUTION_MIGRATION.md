# Authoritative paper execution migration

## Decision
The transactional SQLite paper ledger is the intended authoritative source of simulated fills, cash and positions. The older `PaperAccount` + `PaperCoordinator` + `PaperJournal` path remains only for legacy tests/research and MUST NOT be exposed as an operational order endpoint.

## Completed
- Transactional order/fill accounting and locked risk validation.
- Persistent kill switch and risk reference state.
- Instrument quote-currency registry and quote-age regression checks.
- Direct sanitised snapshot export from transactional fills to the existing read-only dashboard format.

## Not completed
- No single public-facing order API has been established.
- No enforceable ban on calling legacy Python classes from other code.
- No direct publication pipeline from transactional fills.
- No atomic audit log of fills and authorisation decisions.
- No migration of historical legacy journal entries into transactional ledger.
- No production data lineage, source signatures or replay of historical state.

## Safety policy
Do not expose either execution path to subscribers, brokers, AI-generated commands or external requests. Do not merge or deploy until the old path is removed from operational use, all order entrypoints use the same authenticated service, and integration and adversarial tests pass.
