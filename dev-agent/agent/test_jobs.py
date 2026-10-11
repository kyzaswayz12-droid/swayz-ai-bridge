"""Canonical signed test-job envelopes for a trusted worker."""
from dataclasses import dataclass
import hashlib
import hmac
import json
import re

SHA40=re.compile(r"^[a-f0-9]{40}$")
JOB_ID=re.compile(r"^[A-Za-z0-9_-]{1,80}$")

@dataclass(frozen=True)
class TestJob:
    job_id: str
    repository: str
    commit_sha: str
    suite: str

def serialize_job(job: TestJob) -> bytes:
    if not isinstance(job,TestJob) or not isinstance(job.job_id,str) or not JOB_ID.fullmatch(job.job_id):
        raise ValueError("Invalid job identifier")
    if job.repository!="kyzaswayz12-droid/swayz-ai-bridge":
        raise ValueError("Repository not allowlisted")
    if not isinstance(job.commit_sha,str) or not SHA40.fullmatch(job.commit_sha):
        raise ValueError("Invalid commit SHA")
    if job.suite!="python-unittest":
        raise ValueError("Test suite not allowlisted")
    return json.dumps({"job_id":job.job_id,"repository":job.repository,
                       "commit_sha":job.commit_sha,"suite":job.suite},
                      sort_keys=True,separators=(",",":")).encode()

def sign_job(job: TestJob, secret: bytes) -> str:
    if not isinstance(secret,bytes) or len(secret)<32:
        raise ValueError("Worker signing key too short")
    return hmac.new(secret,serialize_job(job),hashlib.sha256).hexdigest()

def verify_job(raw: bytes, signature: str, secret: bytes) -> TestJob:
    if not isinstance(raw,bytes) or len(raw)>2048:
        raise ValueError("Invalid job size")
    if not isinstance(signature,str) or not re.fullmatch(r"[a-f0-9]{64}",signature):
        raise ValueError("Invalid signature")
    if not isinstance(secret,bytes) or len(secret)<32:
        raise ValueError("Worker signing key too short")
    expected=hmac.new(secret,raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,signature):
        raise ValueError("Job authentication failed")
    try:
        doc=json.loads(raw)
    except (ValueError,UnicodeDecodeError):
        raise ValueError("Invalid job JSON") from None
    if not isinstance(doc,dict) or set(doc)!={"job_id","repository","commit_sha","suite"}:
        raise ValueError("Invalid job schema")
    job=TestJob(**doc)
    if serialize_job(job)!=raw:
        raise ValueError("Noncanonical job envelope")
    return job
