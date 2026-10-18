"""Create a disposable, container-readable snapshot from a verified staging tree.

Offline filesystem operation only: never invokes Docker, Git or providers.
Caller must independently authenticate the signed manifest and source.
"""
import os
import stat
from pathlib import Path


def prepare_readonly_snapshot(source, destination, *, expected_files):
    src, dst = Path(source), Path(destination)
    if not src.is_absolute() or not src.is_dir() or src.is_symlink() or src.resolve() != src:
        raise PermissionError("Invalid source directory")
    if not dst.is_absolute() or dst.exists() or dst.is_symlink():
        raise PermissionError("Destination must not exist")
    if not isinstance(expected_files, dict) or not expected_files:
        raise ValueError("Expected file hashes required")
    import hashlib
    validated = {}
    for relative, digest in expected_files.items():
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise ValueError("Invalid relative path")
        rel = Path(relative)
        if rel.is_absolute() or any(part in ("..", ".") for part in rel.parts):
            raise ValueError("Unsafe relative path")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid digest")
        file = src / rel
        if any(part.is_symlink() for part in (file, *file.parents) if part != src and src in part.parents):
            raise PermissionError("Symlink in source path")
        if not file.is_file() or not stat.S_ISREG(file.stat().st_mode):
            raise PermissionError("Invalid source file")
        data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise PermissionError("Source digest mismatch")
        validated[rel] = data
    # Refuse extra files: only manifest-authorised bytes can enter the snapshot.
    actual = {p.relative_to(src) for p in src.rglob("*") if p.is_file()}
    if actual != set(validated):
        raise PermissionError("Source file set mismatch")
    dst.mkdir(mode=0o700)
    try:
        for rel, data in validated.items():
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            os.chmod(target, 0o444)
        for directory in sorted((p for p in dst.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            os.chmod(directory, 0o555)
        os.chmod(dst, 0o555)
    except BaseException:
        # Leave an incomplete snapshot inaccessible, for manual quarantine.
        os.chmod(dst, 0o700)
        raise
    return dst
