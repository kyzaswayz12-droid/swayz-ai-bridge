"""Fail-closed review result validator. Model text is untrusted data."""
import json
import re
from dataclasses import dataclass

HASH=re.compile(r"^[a-f0-9]{64}$")

@dataclass(frozen=True)
class VerifiedReview:
    sha256: str
    approved: bool
    findings: tuple[str,...]

def validate_review(text: str, expected_sha256: str) -> VerifiedReview:
    if not isinstance(text,str) or len(text)>32768 or not HASH.fullmatch(expected_sha256):
        raise ValueError("Invalid review input")
    try:
        data=json.loads(text)
    except ValueError:
        raise ValueError("Review must be JSON") from None
    if not isinstance(data,dict) or set(data)!={"proposal_sha256","approved","findings"}:
        raise ValueError("Invalid review schema")
    if data["proposal_sha256"]!=expected_sha256:
        raise ValueError("Review fingerprint mismatch")
    if type(data["approved"]) is not bool:
        raise ValueError("Approval must be boolean")
    findings=data["findings"]
    if (not isinstance(findings,list) or len(findings)>30 or
        any(not isinstance(x,str) or not x.strip() or len(x)>2000 for x in findings)):
        raise ValueError("Invalid findings")
    if not data["approved"] and not findings:
        raise ValueError("Rejected review requires findings")
    return VerifiedReview(expected_sha256,data["approved"],tuple(findings))
