# Swayz AI Bridge

Prototype single-turn Slack router for OpenAI and Anthropic. **Not deployed or live-tested.**

## How it works
- In the authorised channel, type `chatgpt: hello` or `claude: hello`. These are **literal prefixes**, not Slack @mentions.
- Slack signatures are checked, and bot/edit messages are ignored.
- Both `ALLOWED_CHANNEL_ID` and `ALLOWED_USER_IDS` must be configured. An empty allowlist denies all users.
- SQLite stores duplicate-message claims and UTC daily request counts.
- Paid API calls are **disabled by default**: both daily limits default to 0. Request counts are not monetary caps.
- One response is posted to the originating Slack thread; there are no automatic agent-to-agent conversations.

## Local development
1. Install Python 3.11+: `python -m pip install -r requirements-dev.txt`.
2. Run tests: `python -m pytest -q`.
3. Run the app: `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
4. Build container: `docker build -t swayz-ai-bridge .`.

## Slack and deployment
See [deployment checklist](docs/DEPLOYMENT.md). The Slack app needs `chat:write`, `channels:history`, and `message.channels` for the public test channel. Provide a valid HTTPS `/slack/events` URL. Store secrets only in hosting environment variables.

## Operational limitations
- Single instance and worker only, with SQLite on a persistent writable volume (`/data/bridge.sqlite3` in Docker).
- The mounted `/data` directory must be writable by UID 10001. A Dockerfile `VOLUME` declaration does not provision cloud persistent storage.
- Message delivery is at-most-once. Background tasks are not a durable job queue.
- Configure hard provider-side spend controls and approve the budget before enabling requests.
- No automatic bot-to-bot dialogue, repository modifications, or deployment actions are enabled.
- GitHub Actions tests and Docker build must pass before deployment.

## Planned handoff format
`task_id, thread_id, from, to, goal, context_summary, artifacts, completed, next_action, expected_output, constraints, turn_index, max_turns, requires_approval`
