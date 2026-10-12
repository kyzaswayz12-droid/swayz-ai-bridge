"""Fixed, offline-only Docker invocation specification.

Never executes Docker. A privileged trusted service must separately verify
the signed job, immutable source checkout and staged manifest.
"""
from dataclasses import dataclass

IMAGE="python:3.12.7-slim@sha256:REPLACE_WITH_VERIFIED_DIGEST"
ALLOWED_SUITE=("python3","-m","unittest","discover","-s","tests","-v")

@dataclass(frozen=True)
class ContainerPlan:
    argv: tuple[str,...]
    ready: bool

def restricted_plan(image: str, *, cpu: str="1", memory: str="512m") -> ContainerPlan:
    if not isinstance(image,str) or "@sha256:" not in image:
        raise ValueError("Verified immutable image digest required")
    digest=image.rsplit("@sha256:",1)[1]
    if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid image digest")
    if cpu!="1" or memory!="512m":
        raise ValueError("Unapproved resource limit")
    return ContainerPlan((
        "docker","run","--rm","--network","none","--read-only",
        "--cap-drop","ALL","--security-opt","no-new-privileges",
        "--pids-limit","64","--memory",memory,"--cpus",cpu,
        "--user","65534:65534","--tmpfs","/tmp:rw,noexec,nosuid,size=64m",
        "--workdir","/work",image,*ALLOWED_SUITE),True)
