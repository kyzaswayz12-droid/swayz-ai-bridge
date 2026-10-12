"""Offline source-commit provenance check.

Requires a trusted immutable checkout prepared by the worker. This module
does not fetch source, authenticate GitHub or execute subprocesses.
"""
import re
from pathlib import Path

_SHA = re.compile(r"^[a-f0-9]{40}$")


def verify_checkout_provenance(*, expected_commit: str, observed_commit: str,
                               workspace: str, approved_root: str) -> bool:
    if not isinstance(expected_commit, str) or not _SHA.fullmatch(expected_commit):
        raise ValueError("Invalid expected commit")
    if not isinstance(observed_commit, str) or not _SHA.fullmatch(observed_commit):
        raise ValueError("Invalid observed commit")
    if expected_commit != observed_commit:
        raise PermissionError("Source commit mismatch")
    root = Path(approved_root)
    work = Path(workspace)
    if not root.is_absolute() or not work.is_absolute():
        raise ValueError("Absolute paths required")
    if root.is_symlink() or work.is_symlink() or not root.is_dir() or not work.is_dir():
        raise PermissionError("Invalid checkout directory")
    if root.resolve() != root or work.resolve() != work:
        raise PermissionError("Noncanonical checkout path")
    if not work.is_relative_to(root) or work == root:
        raise PermissionError("Workspace outside approved root")
    return True
