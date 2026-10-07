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

## Docker volume and HTTPS

The image defaults to `BRIDGE_DB_PATH=/data/bridge.sqlite3`. Before running it, mount a **persistent** local filesystem volume at `/data` and ensure the mount directory is writable by UID 10001 (for example, on a controlled Linux host: `chown 10001:10001 /path/to/bridge-data`). The Dockerfile `VOLUME` declaration alone does **not** create a durable DigitalOcean volume. Do not use multiple replicas or NFS-mounted SQLite state.

Terminate HTTPS using a configured reverse proxy (e.g. Caddy or nginx) with a valid certificate and proxy requests to the container's port 8000. Never expose the application directly to the public internet without HTTPS.

**Stop switch:** set either daily limit to 0 and restart/redeploy; alternatively revoke provider API keys or remove the Slack app from the test channel. Environment variables do not automatically update in a running container.

**Current status:** No DigitalOcean service has been created, no Slack app credentials are configured, and no live provider calls have been verified.
