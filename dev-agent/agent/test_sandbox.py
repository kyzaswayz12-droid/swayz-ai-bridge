"""Build an immutable, restricted Docker test invocation.

The returned argv is data only. No subprocess is started in this module.
A dedicated worker must validate isolation and execute it separately.
"""
from dataclasses import dataclass
from pathlib import Path
import re

PINNED_IMAGE = "python:3.12.7-slim-bookworm@sha256:" + "0"*64

@dataclass(frozen=True)
class TestInvocation:
    argv: tuple[str, ...]
    workspace: str

def build_test_invocation(workspace: str, *, image: str,
                          memory_mb: int = 512, cpus: str = "1.0") -> TestInvocation:
    root = Path(workspace)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("Invalid workspace")
    if root.resolve() != root:
        raise ValueError("Workspace must be canonical")
    # Image digest must be set to an explicitly approved real digest in
    # deployment configuration; tags and placeholders are never accepted.
    if not re.fullmatch(r"python:3\.12(?:\.[0-9]+)?-slim-bookworm@sha256:[a-f0-9]{64}",image):
        raise ValueError("Pinned Python image required")
    if image.endswith("0"*64):
        raise ValueError("Placeholder image digest forbidden")
    if type(memory_mb) is not int or not 256 <= memory_mb <= 1024:
        raise ValueError("Invalid memory limit")
    if cpus not in ("0.5","1.0"):
        raise ValueError("Invalid CPU limit")
    return TestInvocation((
        "docker","run","--rm","--network=none","--read-only",
        "--cap-drop=ALL","--security-opt=no-new-privileges",
        "--pids-limit=128","--memory",f"{memory_mb}m",
        "--cpus",cpus,"--user","65534:65534",
        "--mount",f"type=bind,src={root},dst=/src,readonly",
        "--tmpfs","/tmp:rw,nosuid,nodev,noexec,size=64m",
        "--workdir","/src",image,
        "python","-m","unittest","discover","-s","tests","-v"
    ),str(root))
