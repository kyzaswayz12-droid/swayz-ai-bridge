"""Bridge-local TLS authenticated control client. No Docker privileges."""
import hashlib
import hmac
import json
import re
import secrets
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
        self.key = key
        self.ca_file = str(path)

    def request(self, action, *, job_id=None):
        if action not in ("status", "stop", "job_status"):
            raise PermissionError("Unsupported control action")
        if action == "job_status":
            if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
                raise ValueError("Invalid job ID")
        elif job_id is not None:
            raise ValueError("Unexpected job ID")
        body = json.dumps({"action": action, "job_id": job_id,
                           "nonce": secrets.token_hex(16),
                           "timestamp": int(time.time())},
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
        return data
