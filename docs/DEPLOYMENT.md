# Deployment checklist (not yet deployed)

## Prerequisites
- Private repository, verified GitHub Actions tests and independent security review
- DigitalOcean account and explicit approval for a paid service
- OpenAI and Anthropic API accounts with billing limits
- A dedicated Slack app restricted to #ai-projects; do not reuse personal user tokens

## Slack configuration
- Slack Events API request URL: `https://YOUR_HOST/slack/events`
- Bot scopes: `chat:write`, `channels:history`
- Subscribe to `message.channels`
- Invite bot to #ai-projects
- Only plain `chatgpt:` and `claude:` commands route; Slack @mentions are not yet supported.

## Environment secrets
Configure via DigitalOcean secret variables, never GitHub commits:
`SLACK_SIGNING_SECRET`, `SLACK_BOT_TOKEN`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `OPENAI_MODEL`, `ANTHROPIC_MODEL`.
Configure nonsecret `ALLOWED_CHANNEL_ID`, `ALLOWED_USER_IDS`,
`DAILY_LIMIT_PER_USER`, `DAILY_LIMIT_TOTAL`, `BRIDGE_DB_PATH=/data/bridge.sqlite3`.
An empty allowed-user list denies all calls.

## Persistence and safety
- One instance / one worker only; attach a persistent writable volume at /data.
- A container without persistent storage loses deduplication and daily usage state on restart.
- Per-request caps do **not** guarantee a monetary budget. Set hard spending controls at API providers and add token-cost accounting before enabling autonomous handoffs.
- No automatic bot-to-bot messages, GitHub writes or paid deployment without separate approval.
- Validate signing, user restrictions, duplicate delivery and failure handling in staging before production.
- Check model IDs against each provider's current API documentation.

## Safe default

Model requests are disabled by default (daily limits = 0). Explicitly set both daily limits only after billing controls and an approved budget are configured. Request caps are not hard monetary caps.
