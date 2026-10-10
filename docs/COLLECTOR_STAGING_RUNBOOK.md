# Kraken public quote collector — manual staging

**No deployment has been performed.** This is a proposed, operator-approved one-shot test.

## Image
```bash
docker build -f Dockerfile.collector -t swayz-market-collector:staging .
```

## Preflight
- Verify the live Slack bridge remains healthy.
- Create a dedicated directory owned by UID 10003, separate from `/opt/swayz-data`.
- Do not pass API keys or secrets to this container.
- Check the Kraken public API endpoint and rate-limit policy.
- Confirm the selected pair is supported and the host clock is accurate.

## Proposed single observation
```bash
docker run --rm --name swayz-collector-once \
  --network bridge \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --security-opt no-new-privileges \
  -v /opt/swayz-market-staging:/data \
  swayz-market-collector:staging \
  --pair XBTUSD --state-db /data/state.sqlite3 --archive-db /data/quotes.sqlite3
```

This runs once and exits. It requires outbound HTTPS to the Kraken public API and does not use trading permissions.

## Acceptance criteria
- Valid public quote received and stored with observation timestamp.
- No credentials or private endpoints used.
- No repeated polling or retries.
- Quote passes freshness and spread checks.
- Subsequent attempt inside the minimum interval is rejected.
- Existing Slack bridge and dashboard remain unaffected.

## Limitations
The prototype has no exchange-time validation, quote provenance signatures, external monitoring or durable scheduler. A single public ticker observation is not executable liquidity.
