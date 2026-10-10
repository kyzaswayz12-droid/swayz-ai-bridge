# GitHub–Claude review bridge (development design)

## Objective
On an eligible pull-request update, prepare a bounded review task so Claude can inspect actual source changes, not merely a Slack message.

## Phase 1 — committed
- Verify GitHub `X-Hub-Signature-256` against raw request body.
- Allowlist exact repository, base branches, event types and same-repository PR heads.
- Deduplicate review candidates by repository, PR number and head SHA.
- Queue candidates as pending; require explicit approval before any AI call.

## Phase 2 — not yet implemented
- Add a dedicated `/github/events` endpoint, with an independent webhook secret and payload-size cap.
- Verify delivery identifiers and event replay limits.
- Retrieve the exact commit diff with a GitHub App token scoped to read-only repository contents and pull requests.
- Reject oversized diffs, binary patches, secret-bearing content and suspicious prompt-injection instructions.
- Send only approved bounded diffs to Anthropic with a strict review-only system prompt.
- Persist findings and costs; post an owner-visible report without allowing model-initiated writes.
- Apply per-day spending caps and queue limits.

## Security constraints
- Never send GitHub, Slack, broker, or AI API secrets to a model.
- Never allow webhook payload content to choose the target repository.
- Never allow Claude's review to directly merge, deploy or trade.
- Never accept bot-authored Slack commands as a workaround.
- Keep GitHub webhook delivery separate from Slack events.
- No production configuration or DigitalOcean deployment in this branch.
