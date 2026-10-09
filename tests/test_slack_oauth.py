"""Offline tests for OAuth rejection and one-time state guards."""
import asyncio
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from app.slack_oauth import oauth_callback, oauth_start, create_oauth_state


class FakeRequest:
    def __init__(self, **params):
        self.query_params = params
        self.headers = {}


class OAuthGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "state.json"
        self.state.write_text(json.dumps({"state": "secret-state", "expires_at": time.time() + 300}))
        self.env = patch.dict(os.environ, {"SLACK_OAUTH_STATE_PATH": str(self.state),
            "SLACK_CLIENT_ID": "", "SLACK_CLIENT_SECRET": "",
            "SLACK_OAUTH_REDIRECT_URI": "", "SLACK_OAUTH_TOKEN_PATH": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def assert_rejected(self, status, **params):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(oauth_callback(FakeRequest(**params)))
        self.assertEqual(raised.exception.status_code, status)

    def test_state_creation_is_private_and_unique(self):
        first = Path(self.temp.name) / "new-state.json"
        token = create_oauth_state(first)
        record = json.loads(first.read_text())
        self.assertEqual(token, record["state"])
        self.assertGreater(record["expires_at"], time.time())
        self.assertEqual(first.stat().st_mode & 0o777, 0o600)
        self.assertGreaterEqual(len(token), 32)
        with self.assertRaises(FileExistsError):
            create_oauth_state(first)
        second = create_oauth_state(Path(self.temp.name) / "other-state.json")
        self.assertNotEqual(token, second)

    def test_state_ttl_bounds(self):
        with self.assertRaises(ValueError):
            create_oauth_state(Path(self.temp.name) / "short.json", 5)

    def test_start_requires_admin_token(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(oauth_start(FakeRequest()))
        self.assertEqual(raised.exception.status_code, 403)

    def test_start_generates_authorization_link(self):
        from urllib.parse import urlparse, parse_qs
        state_file = Path(self.temp.name) / "install-state.json"
        token_file = Path(self.temp.name) / "bot.json"
        req = FakeRequest()
        req.headers = {"authorization": "Bearer admin-secret"}
        with patch.dict(os.environ, {
            "SLACK_OAUTH_ADMIN_TOKEN": "admin-secret",
            "SLACK_OAUTH_STATE_PATH": str(state_file),
            "SLACK_CLIENT_ID": "client-id",
            "SLACK_OAUTH_REDIRECT_URI": "https://example.com/slack/oauth/callback",
            "SLACK_OAUTH_SCOPES": "chat:write,channels:history",
            "SLACK_OAUTH_TOKEN_PATH": str(token_file),
        }):
            link = asyncio.run(oauth_start(req))
            params = parse_qs(urlparse(link).query)
            self.assertEqual(params["state"][0], json.loads(state_file.read_text())["state"])
            self.assertEqual(params["scope"][0], "chat:write,channels:history")
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(oauth_start(req))
            self.assertEqual(raised.exception.status_code, 409)

    def test_wrong_state(self):
        self.assert_rejected(403, state="wrong", code="test")

    def test_expired_state(self):
        self.state.write_text(json.dumps({"state": "secret-state", "expires_at": time.time() - 1}))
        self.assert_rejected(403, state="secret-state", code="test")

    def test_missing_code(self):
        self.assert_rejected(400, state="secret-state")

    def test_missing_configuration(self):
        self.assert_rejected(503, state="secret-state", code="test")

    def test_claim_prevents_reuse(self):
        with patch.dict(os.environ, {"SLACK_CLIENT_ID": "id", "SLACK_CLIENT_SECRET": "secret",
            "SLACK_OAUTH_REDIRECT_URI": "https://example.com/callback",
            "SLACK_OAUTH_TOKEN_PATH": str(Path(self.temp.name) / "token.json")}):
            Path(str(self.state) + ".claimed").touch()
            self.assert_rejected(409, state="secret-state", code="test")


if __name__ == "__main__":
    unittest.main()
