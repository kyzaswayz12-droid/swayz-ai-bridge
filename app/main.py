"""Single-turn Slack AI router. Prototype: use only in a restricted test channel."""
import hashlib
import hmac
import os
import time
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
import httpx

app = FastAPI(title="Swayz AI Bridge")
processed_events: set[str] = set()  # Non-durable; replace with Redis before production.


def valid_signature(body: bytes, timestamp: str, signature: str, secret: str, now: float | None = None) -> bool:
    if not (secret and timestamp and signature):
        return False
    try:
        if abs((time.time() if now is None else now) - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    digest = hmac.new(secret.encode(), b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("v0=" + digest, signature)


def route(text: str) -> tuple[str, str] | None:
    for prefix, provider in (("@chatgpt ", "openai"), ("@claude ", "anthropic")):
        if text.lower().startswith(prefix):
            prompt = text[len(prefix):].strip()
            if prompt and len(prompt) <= 4000:
                return provider, prompt
    return None


async def generate(provider: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=45) as client:
        if provider == "openai":
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
                json={"model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
                      "messages": [{"role": "system", "content": "You are a concise assistant in a Slack test channel. Never claim to have performed external actions."},
                                   {"role": "user", "content": prompt}], "max_tokens": 450},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"] or "(empty response)"
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
            json={"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                  "max_tokens": 450, "messages": [{"role": "user", "content": prompt}]},
        )
        response.raise_for_status()
        return "".join(part["text"] for part in response.json()["content"] if part["type"] == "text")


async def process_message(channel: str, thread_ts: str, provider: str, prompt: str) -> None:
    try:
        answer = await generate(provider, prompt)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": "Bearer " + os.environ["SLACK_BOT_TOKEN"]},
                json={"channel": channel, "thread_ts": thread_ts, "text": answer[:3500]},
            )
            response.raise_for_status()
            if not response.json().get("ok"):
                raise RuntimeError("Slack API rejected message")
    except Exception:
        # Do not log credentials or provider response bodies.
        app.state.last_error = "Processing failed; check provider configuration"


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    if not valid_signature(body, request.headers.get("x-slack-request-timestamp", ""),
                           request.headers.get("x-slack-signature", ""),
                           os.environ.get("SLACK_SIGNING_SECRET", "")):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    payload = await request.json()
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    event = payload.get("event", {})
    if payload.get("type") != "event_callback" or event.get("type") != "message":
        return {"ok": True}
    # Ignore bots, edits, deletes, and anything outside our explicitly allowed channel.
    if event.get("bot_id") or event.get("subtype") or not event.get("user"):
        return {"ok": True}
    channel = event.get("channel")
    if not os.environ.get("ALLOWED_CHANNEL_ID") or channel != os.environ["ALLOWED_CHANNEL_ID"]:
        return {"ok": True}
    selected = route(event.get("text", ""))
    event_id = payload.get("event_id")
    if not selected or not event_id or event_id in processed_events:
        return {"ok": True}
    processed_events.add(event_id)
    provider, prompt = selected
    background_tasks.add_task(process_message, channel, event.get("thread_ts") or event["ts"], provider, prompt)
    return {"ok": True}
