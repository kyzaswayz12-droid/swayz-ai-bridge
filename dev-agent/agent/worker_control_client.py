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

    def request(self, action, *, job_id=None, task=None):
        if action not in {"status", "stop", "job_status", "develop"}:
            raise PermissionError("Unsupported control action")
        if action in {"job_status", "develop"}:
            import re
            if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
                raise ValueError("Invalid job ID")
        elif job_id is not None:
            raise ValueError("Unexpected job ID")
        if action == "develop":
            if not isinstance(task, str) or not 1 <= len(task.strip()) <= 400:
                raise ValueError("Invalid task")
        elif task is not None:
            raise ValueError("Unexpected task")
        data = {"action": action, "job_id": job_id,
                "nonce": secrets.token_hex(16), "timestamp": int(time.time())}
        if action == "develop":
            data["task"] = task.strip()
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
            if action in {"status", "stop"} and type(result.get("stopped")) is not bool:
                raise ValueError("Invalid worker stop state")
            if action == "develop" and (result.get("job_id") != job_id or result.get("state") != "queued"):
                raise ValueError("Task admission not confirmed")
            if action == "job_status" and (result.get("job_id") != job_id or
                                           not isinstance(result.get("state"), str)):
                raise ValueError("Invalid worker job status")
            return result
