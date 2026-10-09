"""One-time Slack OAuth callback. Requires server-side state and private token volume."""
import hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

router = APIRouter()
log = logging.getLogger("swayz.oauth")


def create_oauth_state(path: Path, ttl_seconds: int = 600) -> str:
    """Create an unpredictable one-time state; never print it in application logs."""
    if not 60 <= ttl_seconds <= 900:
        raise ValueError("OAuth state lifetime must be 60-900 seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    state = secrets.token_urlsafe(32)
    payload = json.dumps({"state": state, "expires_at": time.time() + ttl_seconds})
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return state


@router.get("/slack/oauth/callback", response_class=PlainTextResponse)
async def oauth_callback(request: Request):
    # A state file contains JSON {"state": "...", "expires_at": unix_seconds}.
    # A one-time exclusive claim prevents simultaneous requests consuming the same state.
    state_path = os.environ.get("SLACK_OAUTH_STATE_PATH", "")
    supplied = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    if not state_path or not supplied:
        raise HTTPException(status_code=403, detail="Invalid OAuth state")
    state_file = Path(state_path)
    try:
        state_data = json.loads(state_file.read_text(encoding="utf-8"))
        expected = state_data.get("state", "")
        expiry = float(state_data.get("expires_at", 0))
    except (OSError, ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Invalid OAuth state")
    if not isinstance(expected, str) or not expected or not hmac.compare_digest(expected, supplied) or time.time() >= expiry:
        raise HTTPException(status_code=403, detail="Invalid OAuth state")
    if request.query_params.get("error"):
        raise HTTPException(status_code=400, detail="Slack authorisation declined")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorisation code")

    client_id = os.environ.get("SLACK_CLIENT_ID", "")
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("SLACK_OAUTH_REDIRECT_URI", "")
    output = os.environ.get("SLACK_OAUTH_TOKEN_PATH", "")
    if not all((client_id, client_secret, redirect_uri, output)):
        raise HTTPException(status_code=503, detail="OAuth not configured")
    if Path(output).exists():
        raise HTTPException(status_code=409, detail="Installation already recorded")
    # Atomically claim installation; remove state before exchanging the code.
    claim_path = state_path + ".claimed"
    try:
        fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="OAuth attempt already in progress")
    try:
        # Recheck state after claiming, then consume it.
        latest = json.loads(state_file.read_text(encoding="utf-8"))
        if latest != state_data or time.time() >= expiry:
            raise HTTPException(status_code=403, detail="Invalid OAuth state")
        state_file.unlink()
    except (OSError, ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Invalid OAuth state")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={"client_id": client_id, "client_secret": client_secret,
                      "code": code, "redirect_uri": redirect_uri},
            )
            response.raise_for_status()
            result = response.json()
        token = result.get("access_token")
        if not result.get("ok") or not isinstance(token, str) or not token.startswith("xoxb-"):
            log.warning("Slack OAuth exchange rejected")
            raise HTTPException(status_code=400, detail="Slack authorisation unsuccessful")
        # Exclusive creation, private permissions; never log credentials.
        path = Path(output)
        with path.open("x", encoding="utf-8", opener=lambda p, flags: os.open(p, flags, 0o600)) as f:
            json.dump({"SLACK_BOT_TOKEN": token, "team_id": result.get("team", {}).get("id"),
                       "app_id": result.get("app_id")}, f)
        return "Slack authorised. Bot token saved securely on the server."
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Installation already recorded")
    except httpx.HTTPError:
        log.error("Slack OAuth transport failure")
        raise HTTPException(status_code=502, detail="Slack authorisation unavailable")
