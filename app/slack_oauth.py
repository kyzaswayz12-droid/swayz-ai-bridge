"""One-time Slack OAuth callback. Requires server-side state and private token volume."""
import hmac
import json
import logging
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

router = APIRouter()
log = logging.getLogger("swayz.oauth")


@router.get("/slack/oauth/callback", response_class=PlainTextResponse)
async def oauth_callback(request: Request):
    # State is generated independently and stored on the server before authorisation.
    expected = os.environ.get("SLACK_OAUTH_STATE", "")
    supplied = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
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
