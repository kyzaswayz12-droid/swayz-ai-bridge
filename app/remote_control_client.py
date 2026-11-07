"""Bridge-local TLS authenticated control client. No Docker privileges."""
import hashlib
import hmac
import json
import re
import secrets
import stat
import time
from pathlib import Path
import httpx

_ENDPOINT = "https://10.106.0.3:8443/control"
_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class RemoteControlClient:
    def __init__(self, *, key, ca_file):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("Invalid control key")
        path = Path(ca_file)
        if path.is_symlink() or not path.is_file():
            raise ValueError("CA certificate required")
        if path.stat().st_mode & 0o022:
            raise ValueError("CA certificate must not be writable by group or others")
        self.key = key
        self.ca_file = str(path)

    def request(self, action, *, job_id=None, task=None):
        if action not in ("status", "stop", "job_status", "develop", "stage"):
            raise PermissionError("Unsupported control action")
        if action in ("job_status", "develop", "stage"):
            if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
                raise ValueError("Invalid job ID")
        elif job_id is not None:
            raise ValueError("Unexpected job ID")
        if action in ("develop", "stage"):
            if not isinstance(task, str) or not 1 <= len(task.strip()) <= 400:
                raise ValueError("Invalid development task")
        elif task is not None:
            raise ValueError("Unexpected task")
        payload = {"action": action, "job_id": job_id,
                   "nonce": secrets.token_hex(16), "timestamp": int(time.time())}
        if action in ("develop", "stage"):
            payload["task"] = task.strip()
        body = json.dumps(payload,
                          sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        signature = hmac.new(self.key, b"SWAYZ-CONTROL-V1\0" + body,
                             hashlib.sha256).hexdigest()
        with httpx.Client(verify=self.ca_file, trust_env=False, timeout=5,
                          follow_redirects=False) as client:
            response = client.post(_ENDPOINT, content=body,
                                   headers={"Content-Type": "application/json",
                                            "X-Swayz-Signature": signature})
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict) or data.get("action") != action:
            raise ValueError("Unexpected control response")
        if action in ("status", "stop") and type(data.get("stopped")) is not bool:
            raise ValueError("Invalid worker stop state")
        if action == "job_status" and (data.get("job_id") != job_id or
                                       data.get("state") not in ("not_found", "queued", "claimed", "done", "admitted", "running", "passed", "failed", "blocked")):
            raise ValueError("Invalid worker job state")
        if action == "develop" and (data.get("job_id") != job_id or data.get("state") != "queued"):
            raise ValueError("Development admission not confirmed")
        if action == "stage" and (data.get("job_id") != job_id or data.get("state") != "held"):
            raise ValueError("Held staging not confirmed")
        return data
