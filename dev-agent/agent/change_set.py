"""Fail-closed validation of proposed coding changes. No code execution or Git writes."""
from pathlib import PurePosixPath

MAX_FILES=12
MAX_BYTES=65536
ALLOWED_SUFFIXES={".py",".md",".json",".toml",".yaml",".yml"}

def validate_change_set(changes):
    if not isinstance(changes,dict) or not 1<=len(changes)<=MAX_FILES:
        raise ValueError("Invalid change count")
    total=0
    normalized={}
    for name,body in changes.items():
        if not isinstance(name,str) or not isinstance(body,str):
            raise ValueError("Invalid change")
        if "\\" in name or "\x00" in name or name.startswith("/") or len(name)>180:
            raise ValueError("Unsafe path")
        path=PurePosixPath(name)
        if any(part in ("..",".","") for part in name.split("/")) or path.is_absolute():
            raise ValueError("Path traversal")
        if path.suffix not in ALLOWED_SUFFIXES:
            raise ValueError("Disallowed extension")
        if any(part.startswith(".") for part in path.parts):
            raise ValueError("Hidden paths forbidden")
        if any(part.lower() in ("secrets","credentials",".git","node_modules") for part in path.parts):
            raise ValueError("Protected directory")
        size=len(body.encode("utf-8"))
        if size>MAX_BYTES:
            raise ValueError("File too large")
        total+=size
        normalized[str(path)]=body
    if total>MAX_BYTES:
        raise ValueError("Change set too large")
    return normalized
