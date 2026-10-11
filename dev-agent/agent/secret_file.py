"""Strict credential-file loader for the isolated development agent.

Never prints credentials, executes shell, or reads from the Git checkout.
"""
from pathlib import Path
import os
import stat

NAMES = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")

def load_provider_keys(path: str | Path) -> dict[str, str]:
    p = Path(path).expanduser()
    if p.is_symlink() or not p.is_file():
        raise ValueError("Credential file missing or symlinked")
    info = p.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
        raise PermissionError("Credential file must be owned by current user")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise PermissionError("Credential file must have permissions 0600")
    if info.st_size > 8192:
        raise ValueError("Credential file too large")
    result = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Malformed credential entry")
        name, value = line.split("=", 1)
        name = name.strip()
        if name not in NAMES or name in result:
            raise ValueError("Unknown or duplicate credential entry")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not value or any(c.isspace() for c in value):
            raise ValueError("Invalid credential value")
        result[name] = value
    if set(result) != set(NAMES):
        raise ValueError("Both provider credentials are required")
    return result
