"""Preflight staging paths against ancestor symlinks and public directories."""
import os
import stat
from pathlib import Path

def verify_private_parent(parent):
    path=Path(parent)
    if not path.is_absolute():
        raise PermissionError("Absolute staging path required")
    for candidate in (path,*path.parents):
        if candidate.is_symlink():
            raise PermissionError("Symlink ancestor forbidden")
    if not path.is_dir():
        raise PermissionError("Staging parent missing")
    info=path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid():
        raise PermissionError("Staging parent must belong to worker")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise PermissionError("Staging parent must be private")
    return path
