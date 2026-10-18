"""Recheck a disposable worker snapshot against its authorised SHA-256 manifest.

Offline verification only. Production execution still requires race-resistant
filesystem isolation, image approval and a separate trusted Docker service.
"""
import hashlib
import os
import stat
from pathlib import Path


def verify_snapshot_before_execution(snapshot, expected_hashes):
    root = Path(snapshot)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise PermissionError("Invalid snapshot")
    if root.resolve() != root or root.stat().st_mode & 0o222:
        raise PermissionError("Writable or noncanonical snapshot")
    if not isinstance(expected_hashes, dict) or not expected_hashes:
        raise ValueError("Expected hashes required")
    actual = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            item = Path(base) / name
            if item.is_symlink():
                raise PermissionError("Snapshot symlink forbidden")
            if item.stat().st_mode & 0o222:
                raise PermissionError("Writable snapshot entry")
        for name in files:
            item = Path(base) / name
            if not stat.S_ISREG(item.stat().st_mode):
                raise PermissionError("Non-regular snapshot entry")
            actual[item.relative_to(root).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    if actual != expected_hashes:
        raise PermissionError("Snapshot manifest mismatch")
    return True
