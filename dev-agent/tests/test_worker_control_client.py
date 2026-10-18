import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.worker_control_client import WorkerControlClient


class WorkerControlClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ca = Path(self.tmp.name) / "ca.pem"
        self.ca.write_text("test ca")
        self.client = WorkerControlClient(
            endpoint="https://10.106.0.3:8443/control", key=b"k" * 32,
            ca_file=self.ca)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reject_public_endpoint(self):
        with self.assertRaises(ValueError):
            WorkerControlClient(endpoint="https://0.0.0.0:8443/control",
                                key=b"k" * 32, ca_file=self.ca)

    def test_reject_short_key(self):
        with self.assertRaises(ValueError):
            WorkerControlClient(endpoint="https://10.106.0.3:8443/control",
                                key=b"k", ca_file=self.ca)

    def test_reject_missing_ca(self):
        with self.assertRaises(ValueError):
            WorkerControlClient(endpoint="https://10.106.0.3:8443/control",
                                key=b"k" * 32, ca_file=self.ca.parent / "missing")

    def test_no_enable(self):
        with self.assertRaises(PermissionError):
            self.client.request("enable")

    def test_job_id_validation(self):
        with self.assertRaises(ValueError):
            self.client.request("job_status", job_id="../bad")

    @patch("agent.worker_control_client.httpx.Client")
    def test_tls_verified_and_no_retries(self, mock_client):
        transport = mock_client.return_value.__enter__.return_value
        response = MagicMock()
        response.json.return_value = {"action": "status", "stopped": True}
        transport.post.return_value = response
        result = self.client.request("status")
        self.assertTrue(result["stopped"])
        self.assertEqual(mock_client.call_args.kwargs["verify"], str(self.ca))
        self.assertFalse(mock_client.call_args.kwargs["follow_redirects"])
        self.assertFalse(mock_client.call_args.kwargs["trust_env"])
        self.assertEqual(transport.post.call_count, 1)

    @patch("agent.worker_control_client.httpx.Client")
    def test_invalid_response_rejected(self, mock_client):
        transport = mock_client.return_value.__enter__.return_value
        transport.post.return_value.json.return_value = {"action": "enable"}
        with self.assertRaises(ValueError):
            self.client.request("status")
