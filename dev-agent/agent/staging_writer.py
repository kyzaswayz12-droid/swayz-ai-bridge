"""Stage validated proposals in a private new directory; never execute files."""
import os
from pathlib import Path
from .change_set import validate_change_set

def stage_changes(parent, job_id, changes):
    changes=validate_change_set(changes)
    if not isinstance(job_id,str) or not job_id.isascii() or not (1<=len(job_id)<=64) or not all(c.isalnum() or c in "-_" for c in job_id):
        raise ValueError("Invalid job ID")
    parent=Path(parent)
    if parent.is_symlink() or not parent.is_dir() or parent.stat().st_mode & 0o077:
        raise PermissionError("Private staging parent required")
    root=parent/job_id
    root.mkdir(mode=0o700)
    for name,body in changes.items():
        current=root
        parts=name.split("/")
        for part in parts[:-1]:
            current=current/part
            if not current.exists():
                current.mkdir(mode=0o700)
            if current.is_symlink() or not current.is_dir():
                raise PermissionError("Unsafe staging path")
        flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
        if hasattr(os,"O_NOFOLLOW"): flags|=os.O_NOFOLLOW
        fd=os.open(current/parts[-1],flags,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            stream.write(body)
    return root
