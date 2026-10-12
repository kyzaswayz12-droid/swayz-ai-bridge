# Swayz autonomous development policy — approved target (2026-10-12)

Status: CONFIGURATION SPECIFICATION ONLY. NOT ACTIVE. No unattended execution is authorised until acceptance tests and security review pass.

## Limits
- Combined OpenAI and Anthropic API cost: GBP 5.00 maximum per UTC calendar day, across all agents, models, requests and retries.
- Maximum 20 AI development jobs admitted per UTC calendar day, including failed and interrupted jobs; durable counters must survive restarts.
- Exchange-rate conversion to GBP must use an approved, timestamped, conservative rate. If unavailable, fail closed.
- Reserve a conservative worst-case GBP cost atomically before each API request. Reconcile actual usage against reservation; no request if maximum potential spend exceeds remaining allowance.
- Enforce request concurrency limits, token/output ceilings, bounded retries, and an independent emergency stop. Do not treat estimated cost as verified actual cost.
- On API usage ambiguity or journal corruption, halt dispatch until reconciled.

## Permitted unattended actions after activation
- Generate and review development proposals.
- Execute fixed, preapproved offline test suites through a separate hardened worker.
- Create new dedicated development branches, commit reviewed changes to those branches, and open draft pull requests.
- Record immutable job IDs, source commit SHA, manifest digest, signatures, costs, logs, outcomes and approvals.

## Prohibited
- Merge to main or protected branches.
- Production deployment, live trading, real-money exchange orders, transfers, or production secret access.
- Unrestricted shell commands, Docker socket access from AI coordinator, unpinned images, network-enabled test containers, privileged containers.
- Modification of spending caps, this policy, security gates, CI protections, or worker permissions by the autonomous agent.

## Activation acceptance gates
1. Trusted service verifies signed job, manifest, source commit, branch scope and immutable container image digest.
2. Read-only disposable workspace, fixed test command, non-root worker, seccomp/AppArmor, no network, capabilities dropped, resource limits.
3. Whole-container termination on timeout, restart orphan cleanup, fail-closed duplicate-job handling.
4. Durable, atomic daily GBP cost reservations and 20-job counter, including concurrent requests, failures, retries, UTC day rollover and restart recovery.
5. Demonstrate rejected tampered manifests, invalid signatures, symlink/path escapes, stale commits, unapproved commands, forbidden GitHub operations.
6. GitHub token permissions restricted to branch and draft PR creation; no autonomous merge or deployment.
7. End-to-end integration tests and manual signoff of activation, with rollback and emergency stop verified.

Do not infer runtime enforcement from this document. No API spending or execution is authorised by the act of committing it.
