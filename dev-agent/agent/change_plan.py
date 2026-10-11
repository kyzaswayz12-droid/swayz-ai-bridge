"""Validate a proposed development change before any GitHub write.

This module never runs git commands or contacts GitHub.
"""
from dataclasses import dataclass
import hashlib
import json
import re

SHA40=re.compile(r"^[a-f0-9]{40}$")
SHA64=re.compile(r"^[a-f0-9]{64}$")
PATH=re.compile(r"^[a-zA-Z0-9_./-]+$")
BLOCKED=(".github/",".git/","secrets/","config/","deploy/")

@dataclass(frozen=True)
class Change:
    path: str
    content: str

@dataclass(frozen=True)
class ApprovedPlan:
    base_sha: str
    proposal_sha256: str
    branch: str
    changes: tuple[Change,...]

def validate_change_plan(raw: str, *, approved_base_sha: str,
                         approved_proposal_sha256: str) -> ApprovedPlan:
    if not isinstance(raw,str) or len(raw.encode("utf-8"))>200000:
        raise ValueError("Invalid change plan size")
    if not SHA40.fullmatch(approved_base_sha) or not SHA64.fullmatch(approved_proposal_sha256):
        raise ValueError("Invalid approval identity")
    try:
        doc=json.loads(raw)
    except (ValueError,TypeError):
        raise ValueError("Change plan must be JSON") from None
    if not isinstance(doc,dict) or set(doc)!={"base_sha","proposal_sha256","branch","changes"}:
        raise ValueError("Invalid change plan schema")
    if doc["base_sha"]!=approved_base_sha or doc["proposal_sha256"]!=approved_proposal_sha256:
        raise ValueError("Change plan does not match approved identity")
    branch=doc["branch"]
    if not isinstance(branch,str) or not re.fullmatch(r"agent/[a-z0-9][a-z0-9-]{0,48}",branch):
        raise ValueError("Unsafe development branch")
    changes=doc["changes"]
    if not isinstance(changes,list) or not 1<=len(changes)<=12:
        raise ValueError("Invalid change count")
    result=[]
    seen=set()
    for item in changes:
        if not isinstance(item,dict) or set(item)!={"path","content"}:
            raise ValueError("Invalid change schema")
        path=item["path"]
        content=item["content"]
        if (not isinstance(path,str) or len(path)>180 or not PATH.fullmatch(path)
            or path.startswith("/") or path.startswith("./") or ".." in path.split("/")
            or path.endswith("/") or path in seen
            or path.startswith(BLOCKED) or path in (".env","Dockerfile")
            or not isinstance(content,str) or len(content.encode("utf-8"))>32768):
            raise ValueError("Unsafe file change")
        seen.add(path)
        result.append(Change(path,content))
    return ApprovedPlan(approved_base_sha,approved_proposal_sha256,branch,tuple(result))

def proposal_digest(text: str) -> str:
    if not isinstance(text,str):
        raise ValueError("Invalid proposal")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
