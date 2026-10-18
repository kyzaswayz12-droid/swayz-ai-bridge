"""TLS-verified, signed worker-control client for the Bridge.

Never disables certificate verification; never automatically retries a control
command. Does not expose job execution, resume, or Docker operations.
"""
import hashlib
import hmac
import ipaddress
import json
import secrets
import time
from pathlib import Path

import httpx


class WorkerControlClient:
    def __init__(self, *, endpoint, key, ca_file, timeout=5.0):
        if endpoint != "https://10.106.0.3:8443/control":
            raise ValueError("Unexpected worker control endpoint")
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("Invalid control key")
        ca = Path(ca_file)
        if ca.is_symlink() or not ca.is_file():
            raise ValueError("Verified TLS CA file required")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 10:
            raise ValueError("Invalid timeout")
        self.endpoint = endpoint
        self._key = key
        self.ca_file = str(ca)
        self.timeout = float(timeout)

    def request(self, action, *, job_id=None):
        if action not in {"status", "stop", "job_status"}:
            raise PermissionError("Unsupported control action")
        if action == "job_status":
            import re
            if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
                raise ValueError("Invalid job ID")
        elif job_id is not None:
            raise ValueError("Unexpected job ID")
        data = {"action": action, "job_id": job_id,
                "nonce": secrets.token_hex(16), "timestamp": int(time.time())}
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        signature = hmac.new(self._key, b"SWAYZ-CONTROL-V1\0" + raw, hashlib.sha256).hexdigest()
        with httpx.Client(verify=self.ca_file, timeout=self.timeout, follow_redirects=False,
                          trust_env=False) as client:
            response = client.post(self.endpoint, content=raw, headers={
                "Content-Type": "application/json", "X-Swayz-Signature": signature})
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or result.get("action") != action:
                raise ValueError("Invalid worker response")
            return result
