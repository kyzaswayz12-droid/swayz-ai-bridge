# Slack app manifest setup

This manifest configures the existing Swayz AI Bridge Slack app. It does not deploy the application or install any credentials.

## Before applying
1. **Do not apply yet** unless the running Docker container has `SLACK_SIGNING_SECRET` configured securely. Otherwise Slack URL verification will fail.
2. The existing app must have its **Signing Secret** installed on the server as a secret environment variable, not committed to GitHub or pasted into chat.
3. Confirm the DuckDNS HTTPS health endpoint returns `{"ok":true}`.
4. Back up the existing Slack app manifest, then merge these settings into the existing app rather than creating a second app.

## Manifest
Use [slack-app-manifest.yaml](../slack-app-manifest.yaml) as the configuration for the existing app. It requests only `chat:write` and `channels:history` for public channels, and subscribes to `message.channels`.

The app uses literal `chatgpt:` and `claude:` prefixes, not Slack @mentions.

## After applying
- Reinstall/re-authorise the app if Slack requests it.
- Invite the app to a dedicated public test channel.
- Obtain the bot token securely from Slack OAuth & Permissions and configure it as `SLACK_BOT_TOKEN` on the server.
- Configure `ALLOWED_CHANNEL_ID` and `ALLOWED_USER_IDS` on the server.
- Leave `DAILY_LIMIT_PER_USER=0` and `DAILY_LIMIT_TOTAL=0` until budget and API provider billing limits are approved.
- Test URL verification, ignored bot messages, authorised users, and error responses before enabling paid calls.

**Security:** If an old DuckDNS account token or Slack verification token was exposed in a screenshot, rotate it. Do not post signing secrets or bot tokens in chat.
