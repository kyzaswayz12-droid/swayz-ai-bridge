"""Offline tests for the packaged Bridge control client.

No network, API spending, Docker execution or production credentials.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.remote_control_client import RemoteControlClient


class BridgeControlClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cert = Path(self.tmp.name) / "worker.crt"
        self.cert.write_text("test-only certificate placeholder")
        self.client = RemoteControlClient(key=b"x" * 32, ca_file=self.cert)

    def tearDown(self):
        self.tmp.cleanup()

    def test_short_key_rejected(self):
        with self.assertRaises(ValueError):
            RemoteControlClient(key=b"x", ca_file=self.cert)

    def test_missing_certificate_rejected(self):
        with self.assertRaises(ValueError):
            RemoteControlClient(key=b"x" * 32, ca_file=self.cert.parent / "missing")

    def test_enable_command_rejected(self):
        with self.assertRaises(PermissionError):
            self.client.request("enable")

    def test_invalid_job_id_rejected(self):
        with self.assertRaises(ValueError):
            self.client.request("job_status", job_id="../escape")

    @patch("app.remote_control_client.httpx.Client")
    def test_private_tls_request_without_redirects(self, mock_http):
        transport = mock_http.return_value.__enter__.return_value
        response = MagicMock()
        response.json.return_value = {"action": "status", "stopped": True}
        transport.post.return_value = response
        result = self.client.request("status")
        self.assertTrue(result["stopped"])
        self.assertEqual(mock_http.call_args.kwargs["verify"], str(self.cert))
        self.assertFalse(mock_http.call_args.kwargs["trust_env"])
        self.assertFalse(mock_http.call_args.kwargs["follow_redirects"])
        self.assertEqual(transport.post.call_count, 1)

    @patch("app.remote_control_client.httpx.Client")
    def test_wrong_action_response_rejected(self, mock_http):
        transport = mock_http.return_value.__enter__.return_value
        transport.post.return_value.json.return_value = {"action": "enable"}
        with self.assertRaises(ValueError):
            self.client.request("status")
