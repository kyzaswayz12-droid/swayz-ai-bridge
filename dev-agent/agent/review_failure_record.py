"""Separate, write-once diagnostic events; proposal checkpoint remains immutable."""
import json
import os
from pathlib import Path

ALLOWED={"review_invalid_json","review_incomplete","review_provider_error"}

def save_review_failure(directory: Path, proposal_sha256: str, reason: str) -> Path:
    if (not isinstance(proposal_sha256,str) or len(proposal_sha256)!=64 or
        any(c not in "0123456789abcdef" for c in proposal_sha256)):
        raise ValueError("Invalid proposal fingerprint")
    if reason not in ALLOWED:
        raise ValueError("Unrecognised failure reason")
    folder=Path(directory)
    if folder.is_symlink() or not folder.is_dir():
        raise PermissionError("Private checkpoint directory missing")
    proposal=folder/(proposal_sha256+".json")
    if not proposal.is_file() or proposal.is_symlink():
        raise PermissionError("Proposal checkpoint missing")
    target=folder/(proposal_sha256+".failure.json")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
    try:
        fd=os.open(target,flags,0o600)
    except FileExistsError:
        return target
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        json.dump({"proposal_sha256":proposal_sha256,
                   "state":"blocked","reason":reason},stream)
    return target
