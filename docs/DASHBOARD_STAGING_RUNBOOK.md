# Swayz Trading — isolated dashboard staging runbook

This is a **review-only** staging plan. Do not deploy without operator approval.

## Preconditions
- Python and dashboard Docker CI checks green for the exact commit.
- Existing Slack bridge health and rollback container verified.
- Snapshot the intended paper journal; do not reuse Slack's `bridge.sqlite3`.
- No OpenAI, Anthropic, Slack, social, broker or payment credentials passed to the dashboard.
- Confirm a dedicated read-only copy of the paper journal is used.
- Ensure port 18080 is bound only to loopback.

## Proposed staging commands (manual approval required)
```bash
docker build -f Dockerfile.dashboard -t swayz-paper-dashboard:staging .
docker run -d --name swayz-paper-dashboard-staging \
  --restart=no \
  -p 127.0.0.1:18080:8080 \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --security-opt no-new-privileges \
  -e PAPER_JOURNAL_PATH=/data/paper.sqlite3 \
  -v /opt/swayz-paper-staging:/data:ro \
  swayz-paper-dashboard:staging
```

These commands are **not yet executed** and the directory and journal copy must first be prepared.

## Validation
- `curl -fsS http://127.0.0.1:18080/health`
- `curl -fsS http://127.0.0.1:18080/api/paper-summary`
- Confirm only simulated records, no secrets, and no private balances.
- Confirm POST /api/orders is 404.
- Confirm Slack bridge still healthy on 127.0.0.1:8000.
- Stop and remove only the staging dashboard container on rollback.

## Limitations
- No public DNS, TLS, access control, subscriber login or production data pipeline.
- Journal projection must be hardened to open immutable read-only SQLite snapshots.
- The dashboard is not approved for public exposure or real-money trading.
