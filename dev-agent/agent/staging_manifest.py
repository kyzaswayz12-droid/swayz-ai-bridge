"""Read-only integrity manifest for staged code; rejects symlinks and mismatches."""
import hashlib
import os
import stat
from pathlib import Path
from .change_set import validate_change_set

def verify_staged_changes(root, changes):
    expected=validate_change_set(changes)
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise PermissionError("Invalid staging root")
    manifest={}
    actual=set()
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name
            if p.is_symlink():
                raise PermissionError("Symlink in staged workspace")
        for name in files:
            p=Path(base)/name
            rel=p.relative_to(root).as_posix()
            if not stat.S_ISREG(p.stat().st_mode):
                raise PermissionError("Non-regular staged file")
            actual.add(rel)
    if actual!=set(expected):
        raise ValueError("Staged file list mismatch")
    for rel,body in expected.items():
        p=root/rel
        raw=p.read_bytes()
        if raw!=body.encode("utf-8"):
            raise ValueError("Staged content mismatch")
        manifest[rel]={"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
    return manifest
