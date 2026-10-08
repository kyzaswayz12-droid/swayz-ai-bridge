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
from app.slack_oauth import oauth_callback


class FakeRequest:
    def __init__(self, **params):
        self.query_params = params


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
