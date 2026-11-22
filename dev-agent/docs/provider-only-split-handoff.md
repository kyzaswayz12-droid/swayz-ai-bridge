# Swayz provider-only split-authority handoff (experimental, NOT deployed)

Status: repository implementation and offline CI tests only. This is NOT
authorisation to start services, reserve a live budget, or make paid requests.
Do not merge or install without a separate operator security review.

## Existing working system is immutable

This feature does NOT modify the installed `/opt/swayz/executor-app`,
`/etc/swayz/executor-signing.key`, `/var/lib/swayzcontrol/state/stop.db`,
the two successful supervised jobs, Slack bridge, Docker, or trading engine.
The Docker signing key MUST NEVER be reused as the provider-grant key.

## Dedicated identities and file ownership

These paths are prerequisites for a future, separate deployment approval:

| Path | Owner | Mode | Purpose |
| --- | --- | --- | --- |
| `/etc/swayz-collaboration/provider-grant-signing.key` | root:root | 0600 | **New independent 32-byte Ed25519 private key** |
| `/var/lib/swayz-provider-grants` | root:root | 0700 | Root-only signed originals |
| `/var/lib/swayz-provider-inbox` | root:swayzdev | 0750 | Cross-identity read-only transfer |
| `/var/lib/swayz-provider-inbox/provider-grant-public.key` | root:swayzdev | 0640 | Pinned 32-byte Ed25519 public key |
| `/run/swayz-provider-proofs` | root:swayzdev | 0750 | Standalone root proof-service socket directory |
| `/run/swayz-provider-proofs/stop-proof.sock` | root:swayzdev | 0660 | Root proof attestation IPC |
| `/home/swayzdev/swayz-agent/data/provider-claims` | swayzdev:swayzdev | 0700 | Persistent no-replay claims |
| `/home/swayzdev/swayz-agent/data/provider-results` | swayzdev:swayzdev | 0700 | Write-once review records |

Use the existing root-owned GBP budget ledger and the **existing** private
`swayzdev` provider credentials file. Never copy credentials into root-owned
directories, change their ownership, or make the GBP ledger group-writable.

## Planned one-shot lifecycle (not yet enabled on Droplet 2)

1. Operator reviews the exact pinned base SHA, approved rate cards, FX approval
   and $0.05 combined *internal reservation estimate*.
2. A separate authenticated root invocation runs
   `deployment/swayz_provider_grant_operator.py --issue-and-publish` and
   explicitly prompts for the job-specific grant. It makes both GBP holds,
   signs a ten-minute task-bound grant using the **dedicated provider-grant
   key**, and copies the unchanged grant into the root-controlled inbox.
   Any uncertain partial issue consumes its identity and needs reconciliation.
3. A separately installed, root-only process runs
   `deployment/swayz_provider_stop_proof_service.py`. It checks the real
   `SO_PEERCRED` against the swayzdev UID, the original signed grant,
   both durable GBP holds and the engaged emergency stop. It issues only
   a 15-second phase-bound stop proof; it never touches provider credentials.
4. The operator invokes `deployment/swayz_provider_worker_one_shot.py`
   **as swayzdev** using its `--execute-paid` gate and exact typed
   confirmation. It verifies the root-pinned public key, grant signature,
   expiry, task, base SHA and one-use claim marker. It asks the root helper for
   a new stop proof immediately before each HTTPS boundary.
5. One GPT-5 Mini response, then at most one Claude Haiku 4.5 review is
   recorded under private write-once checkpoints. Neither process can execute
   generated code, write GitHub, merge, deploy, or live trade.

## Safety and limitations

- All current tests inject fake API replies; **no live model call** has been
  demonstrated through the split-authority system.
- The $0.05 limit is an internal reservation ceiling **not a guaranteed API
  billing cap**. Provider billing must be reconciled separately.
- A 15-second proof attests the emergency stop at issue time; it cannot
  revoke an HTTP request already in flight. Live deployment must undergo an
  additional review of this time-of-check/time-of-use exposure.
- No retries. A failed or uncertain network call leaves holds and claim marker
  intact, pending explicit operator reconciliation.
- The root proof-service configuration, dedicated private/public key pair,
  and ownership layout **do not exist automatically on Droplet 2** merely
  because GitHub CI passes.
- Rate cards/FX approvals have individual expiration dates and must be
  refreshed and independently validated for each new authorised run.
- Do not use `live_collaboration.py` to bypass the shared GBP reservation
  mechanism or release the executor's emergency stop.

## Required next acceptance step before any paid call

On an isolated, supervised deployment window: provision dedicated keys and
directories, validate owner/group/mode via read-only commands, verify that the
root stop-proof socket is callable only by swayzdev, and prove with offline
fake responses that signer/worker run as different UIDs. Then recheck the
actual price and exact proposal cost, request **separate paid authorisation**,
and only then consider one live one-shot. Never reuse completed job IDs.
