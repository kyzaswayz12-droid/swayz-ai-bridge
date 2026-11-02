import os
import tempfile
import unittest
from pathlib import Path
from agent.worker_control_runtime import load_control_runtime_config


class WorkerControlRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cert = root / "cert.pem"
        self.key = root / "key.pem"
        self.auth = root / "auth.key"
        self.cert.write_text("test certificate")
        self.key.write_text("test key")
        self.auth.write_bytes(b"k" * 32)
        for path in (self.cert, self.key, self.auth):
            path.chmod(0o600)
        self.env = dict(
            SWAYZ_CONTROL_ENABLED="1", SWAYZ_CONTROL_BIND="10.106.0.3",
            SWAYZ_CONTROL_PORT="8443",
            SWAYZ_CONTROL_TLS_CERT=str(self.cert),
            SWAYZ_CONTROL_TLS_KEY=str(self.key),
            SWAYZ_CONTROL_AUTH_KEY=str(self.auth),
            SWAYZ_CONTROL_REPLAY_DB=str(root / "replay.db"),
            SWAYZ_CONTROL_STOP_DB=str(root / "stop.db"),
            SWAYZ_CONTROL_JOURNAL_DB=str(root / "journal.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_private_tls_configuration(self):
        config = load_control_runtime_config(self.env)
        self.assertEqual(config.bind_host, "10.106.0.3")
        self.assertEqual(len(config.auth_key), 32)

    def test_disabled_by_default(self):
        with self.assertRaises(PermissionError):
            load_control_runtime_config({**self.env, "SWAYZ_CONTROL_ENABLED": "0"})

    def test_public_bind_rejected(self):
        with self.assertRaises(PermissionError):
            load_control_runtime_config({**self.env, "SWAYZ_CONTROL_BIND": "0.0.0.0"})

    def test_loopback_rejected(self):
        with self.assertRaises(PermissionError):
            load_control_runtime_config({**self.env, "SWAYZ_CONTROL_BIND": "127.0.0.1"})

    def test_wrong_port_rejected(self):
        with self.assertRaises(PermissionError):
            load_control_runtime_config({**self.env, "SWAYZ_CONTROL_PORT": "8000"})

    def test_insecure_key_permissions_rejected(self):
        self.key.chmod(0o666)
        with self.assertRaises(PermissionError):
            load_control_runtime_config(self.env)

    def test_missing_auth_key_rejected(self):
        self.auth.unlink()
        with self.assertRaises(PermissionError):
            load_control_runtime_config(self.env)
