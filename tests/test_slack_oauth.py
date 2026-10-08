"""Offline OAuth guard tests; no Slack calls or secrets required."""
import asyncio
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.slack_oauth import oauth_callback


class FakeRequest:
    def __init__(self, **params):
        self.query_params = params


class OAuthGuardTests(unittest.TestCase):
    def test_missing_state_rejected(self):
        with patch.dict(os.environ, {"SLACK_OAUTH_STATE": "server-generated-state"}):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(oauth_callback(FakeRequest(state="wrong", code="test")))
            self.assertEqual(raised.exception.status_code, 403)

    def test_missing_code_rejected(self):
        with patch.dict(os.environ, {"SLACK_OAUTH_STATE": "server-generated-state"}):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(oauth_callback(FakeRequest(state="server-generated-state")))
            self.assertEqual(raised.exception.status_code, 400)

    def test_missing_configuration_rejected(self):
        env = {"SLACK_OAUTH_STATE": "server-generated-state",
               "SLACK_CLIENT_ID": "", "SLACK_CLIENT_SECRET": "",
               "SLACK_OAUTH_REDIRECT_URI": "", "SLACK_OAUTH_TOKEN_PATH": ""}
        with patch.dict(os.environ, env):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(oauth_callback(FakeRequest(state="server-generated-state", code="test")))
            self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
