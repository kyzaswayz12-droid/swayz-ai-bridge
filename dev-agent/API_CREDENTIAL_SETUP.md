# API credential configuration — Droplet 2

Owner-approved maximum for the Swayz development agent: **USD 5 per UTC day,
combined across OpenAI and Anthropic**.

Important: This is an application-side reservation budget, not a provider-side
hard billing cap. API provider billing may be delayed or may exceed an estimate.
The agent must stop when cost cannot be reconciled.

## Credential handling
- Never paste API keys into ChatGPT, Slack, GitHub, terminal screenshots or logs.
- Use separate, restricted API keys for this development agent.
- Store them in a file outside the Git checkout, accessible only to the
  dedicated service identity (0600 permissions).
- Do not store secrets in a shell history, repository, command-line argument,
  Docker image, or environment dump.
- Configure OpenAI and Anthropic account/project-level spending controls
  and billing alerts independently.
- Use least-privilege credentials, rotate compromised keys, and revoke
  unused keys.

## Live-test gates
1. Confirm all unit tests pass on Droplet 2.
2. Configure provider credentials securely without exposing their values.
3. Confirm provider endpoint access with a single low-token request each.
4. Record actual provider usage and costs, reconciling reservations.
5. Confirm persistent emergency stop is engaged by default.
6. Do not enable recurring background calls until cost accounting and
   restart recovery have been verified.
7. GitHub writes, deployments and live-money trading remain disabled.

**Current state:** The live-test runner is not enabled. This document does
not grant permission to run paid API calls.
