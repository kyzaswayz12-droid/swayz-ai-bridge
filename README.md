# Swayz AI Bridge

A prototype Slack router for OpenAI and Anthropic, **not yet deployed**.

## Features
- Explicit literal prefixes: `@chatgpt your question` or `@claude your question`
- Slack HMAC signature verification and timestamp checks
- Restriction to one configured Slack channel
- One model response per user message, posted in its Slack thread
- Ignores bot messages to prevent automatic bot-to-bot loops

## Setup
1. Install Python 3.11+ and run `pip install -r requirements.txt`.
2. Create a Slack app with Events API, `chat:write`, `channels:history`, and `message.channels` subscription. Invite it to the test channel.
3. Store Slack signing secret, bot token, and model API keys in **host-managed secret environment variables**, using `.env.example` only as a guide. Set `ALLOWED_CHANNEL_ID` to the test channel.
4. Run `uvicorn app.main:app --host 0.0.0.0 --port 8000`, behind HTTPS. Slack event URL: `https://your-host/slack/events`.
5. Run `pytest -q` for unit tests.

## Important limitations
- The code has not been deployed or tested against live Slack/model APIs.
- The prototype recognises literal text prefixes, not Slack autocomplete user mentions.
- FastAPI background tasks and in-memory deduplication are not durable. Add a database, queue, spending limits, monitoring, and approval gates before production.
- No automatic bot-to-bot dialogue or GitHub modifications are enabled.
- Default model IDs may need updating for your API accounts.

## Planned handoff format
`task_id, thread_id, from, to, goal, context_summary, artifacts, completed, next_action, expected_output, constraints, turn_index, max_turns, requires_approval`

## Safe default

Model requests are disabled by default (daily limits = 0). Explicitly set both daily limits only after billing controls and an approved budget are configured. Request caps are not hard monetary caps.
