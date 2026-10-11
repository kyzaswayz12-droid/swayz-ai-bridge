# Provider pricing verification checklist

Before enabling a paid collaboration:
- Confirm the exact OpenAI and Anthropic model IDs.
- Verify USD per-million-token rates directly from each provider's
  current official API pricing page.
- Record the verification date, expiry date, source URL, and owner approval.
- Review any cache, reasoning, tool-use, minimum-charge, or tier-specific
  pricing. The basic input/output rate card does not model these.
- Reject stale or unapproved cards. A reservation is not a provider hard cap.
- Compare request maximum output and bounded input with available daily budget.
- Keep unresolved historical reservations held until billing can be matched.
- Never automatically mark a token-derived estimate as provider-billed spend.

The owner should not store credentials, credit card details or personal
billing information in GitHub rate-card files.
