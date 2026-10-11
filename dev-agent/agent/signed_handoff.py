"""Manifest-bound authenticated test handoff; no execution."""
import hashlib
import hmac
import json
import re
from .test_jobs import TestJob, serialize_job

HEX64=re.compile(r"^[a-f0-9]{64}$")

def sign_manifest_job(job, manifest_sha256, secret):
    if not isinstance(manifest_sha256,str) or not HEX64.fullmatch(manifest_sha256):
        raise ValueError("Invalid manifest")
    if not isinstance(secret,bytes) or len(secret)<32:
        raise ValueError("Invalid secret")
    payload=json.loads(serialize_job(job))
    payload["manifest_sha256"]=manifest_sha256
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    return raw,hmac.new(secret,raw,hashlib.sha256).hexdigest()

def verify_manifest_job(raw,signature,secret,expected_manifest):
    if not isinstance(raw,bytes) or len(raw)>2048 or not isinstance(signature,str) or not HEX64.fullmatch(signature):
        raise ValueError("Invalid envelope")
    if not isinstance(secret,bytes) or len(secret)<32:
        raise ValueError("Invalid secret")
    if not hmac.compare_digest(hmac.new(secret,raw,hashlib.sha256).hexdigest(),signature):
        raise ValueError("Invalid signature")
    if not isinstance(expected_manifest,str) or not HEX64.fullmatch(expected_manifest):
        raise ValueError("Invalid expected manifest")
    try:
        data=json.loads(raw)
    except (ValueError,UnicodeDecodeError):
        raise ValueError("Invalid JSON") from None
    if not isinstance(data,dict) or set(data)!={"job_id","repository","commit_sha","suite","manifest_sha256"}:
        raise ValueError("Invalid schema")
    if data["manifest_sha256"]!=expected_manifest:
        raise ValueError("Manifest mismatch")
    job=TestJob(data["job_id"],data["repository"],data["commit_sha"],data["suite"])
    canonical,_=sign_manifest_job(job,expected_manifest,secret)
    if canonical!=raw:
        raise ValueError("Noncanonical envelope")
    return job
