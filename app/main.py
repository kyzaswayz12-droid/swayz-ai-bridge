"""Single-turn Slack router; restrict to a test channel."""
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from app.slack_oauth import router as slack_oauth_router
from app.core import (
    GENERIC_ERROR_TEXT, MAX_REPLY_CHARS, CallModel, Challenge, MissingConfig,
    Reply, Settings, Store, handle_event, valid_signature,
)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("swayz.bridge")
@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        get_store()
    except Exception as exc:
        logger.critical("state database unavailable error=%s; check BRIDGE_DB_PATH and volume permissions", type(exc).__name__)
        raise
    yield
    store = getattr(app.state, "store", None)
    if store is not None:
        store.close()


app = FastAPI(title="Swayz AI Bridge", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


app.include_router(slack_oauth_router)


def get_store() -> Store:
    store = getattr(app.state, "store", None)
    if store is None:
        store = Store(os.environ.get("BRIDGE_DB_PATH", "bridge.sqlite3"))
        app.state.store = store
    return store


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingConfig(name)
    return value


def describe_error(exc: Exception) -> str:
    if isinstance(exc, MissingConfig):
        return f"missing env var {exc.name}"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"{type(exc).__name__} status={exc.response.status_code}"
    return type(exc).__name__


async def generate(provider: str, prompt: str) -> str:
    instruction = "You are a concise assistant in a Slack test channel. Never claim to have performed external actions."
    async with httpx.AsyncClient(timeout=45) as client:
        if provider == "openai":
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": "Bearer " + require_env("OPENAI_API_KEY")},
                json={"model": require_env("OPENAI_MODEL"),
                      "messages": [{"role": "system", "content": instruction},
                                   {"role": "user", "content": prompt}],
                      "max_completion_tokens": 450},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"] or "(empty response)"
        if provider != "anthropic":
            raise ValueError("Unknown provider")
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": require_env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
            json={"model": require_env("ANTHROPIC_MODEL"), "max_tokens": 450,
                  "system": instruction, "messages": [{"role": "user", "content": prompt}]},
        )
        response.raise_for_status()
        return "".join(part["text"] for part in response.json()["content"] if part["type"] == "text")


async def post_message(channel: str, thread_ts: str, text: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": "Bearer " + require_env("SLACK_BOT_TOKEN")},
                json={"channel": channel, "thread_ts": thread_ts, "text": text[:MAX_REPLY_CHARS]},
            )
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                error_code = str(result.get("error", "unknown"))
                logger.error("slack rejected message error=%s", error_code[:64])
    except Exception as exc:
        logger.error("slack post failed error=%s", describe_error(exc))


async def process_message(channel: str, thread_ts: str, provider: str, prompt: str) -> None:
    try:
        text = await generate(provider, prompt)
    except Exception as exc:
        logger.error("model call failed provider=%s error=%s", provider, describe_error(exc))
        text = GENERIC_ERROR_TEXT
    await post_message(channel, thread_ts, text)


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
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    if isinstance(payload, dict) and payload.get("type") == "url_verification":
        return {"challenge": str(payload.get("challenge", ""))}
    action = handle_event(payload, Settings.from_env(os.environ), get_store(), time.time())
    if isinstance(action, Challenge):
        return {"challenge": action.value}
    if isinstance(action, Reply):
        background_tasks.add_task(post_message, action.channel, action.thread_ts, action.text)
    elif isinstance(action, CallModel):
        background_tasks.add_task(process_message, action.channel, action.thread_ts, action.provider, action.prompt)
    else:
        logger.debug("ignored event reason=%s", action.reason)
    return {"ok": True}
