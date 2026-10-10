"""GitHub webhook authentication and narrow pull-request review eligibility.

Pure functions only: no network, AI requests, Slack posts or repository writes.
"""
import hashlib
import hmac
import json
import re
from dataclasses import dataclass

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[a-f0-9]{40}$")

@dataclass(frozen=True)
class ReviewCandidate:
    repository: str
    pull_number: int
    head_sha: str
    base_ref: str
    event_action: str

def verify_github_signature(body: bytes, signature: str, secret: str) -> bool:
    if not secret or not signature.startswith("sha256="):
        return False
    supplied=signature.removeprefix("sha256=")
    if len(supplied)!=64 or any(c not in "0123456789abcdef" for c in supplied):
        return False
    expected=hmac.new(secret.encode("utf-8"),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied,expected)

def select_review_candidate(body: bytes, event_name: str, *,
                            allowed_repository: str,
                            allowed_base: frozenset[str]) -> ReviewCandidate | None:
    if not _REPO_RE.fullmatch(allowed_repository):
        raise ValueError("Invalid repository allowlist")
    if event_name!="pull_request":
        return None
    try:
        payload=json.loads(body)
    except (ValueError,UnicodeDecodeError):
        raise ValueError("Invalid GitHub event JSON") from None
    if not isinstance(payload,dict) or payload.get("action") not in (
        "opened","reopened","synchronize","ready_for_review"):
        return None
    repository=payload.get("repository")
    pull=payload.get("pull_request")
    if not isinstance(repository,dict) or not isinstance(pull,dict):
        return None
    if repository.get("full_name")!=allowed_repository:
        return None
    number=payload.get("number")
    if type(number) is not int or number<=0 or pull.get("number")!=number:
        return None
    head=pull.get("head")
    base=pull.get("base")
    if not isinstance(head,dict) or not isinstance(base,dict):
        return None
    sha=head.get("sha")
    ref=base.get("ref")
    if not isinstance(sha,str) or not _SHA_RE.fullmatch(sha):
        return None
    if not isinstance(ref,str) or ref not in allowed_base:
        return None
    # Reject forks: external PR source code is untrusted and must not be sent
    # automatically to paid models without separate owner approval.
    head_repo=head.get("repo")
    if not isinstance(head_repo,dict) or head_repo.get("full_name")!=allowed_repository:
        return None
    return ReviewCandidate(allowed_repository,number,sha,ref,payload["action"])
