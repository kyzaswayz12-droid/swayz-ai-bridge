# Swayz Autonomous Development Agent — staging

This directory contains the first integrated, **offline-only** deployment
foundation for Droplet 2. It does not call AI providers or GitHub write APIs.

## Read-only installation smoke test

From the repository root on the non-root `swayzdev` account:

```bash
cd dev-agent
python3 -m unittest discover -s tests -v
python3 -m agent --data-dir ~/swayz-agent/data preflight
python3 -m agent --data-dir ~/swayz-agent/data status
```

The first two commands should succeed without credentials or API charges.
The status command should say `not_initialized` until a task database exists.

## Safety status

- All external actions disabled in `Policy`.
- SQLite task state and audit history implemented.
- Daily estimated cost reservations implemented but **not** a substitute
  for provider-side billing limits.
- No live model dispatch, GitHub mutation, Docker test execution or scheduler.
- No trading broker access, real-money execution or production deployment.

## Next integration gates

1. Import and independently test remaining reviewed agent modules.
2. Wire authenticated model transports with server-side secret storage.
3. Verify Docker sandbox isolation on a dedicated test worker.
4. Add GitHub App least-privilege branch access and draft PR creation.
5. Verify crash recovery, cost reconciliation and emergency stop.
6. Activate only after a bounded end-to-end test and owner approval.
