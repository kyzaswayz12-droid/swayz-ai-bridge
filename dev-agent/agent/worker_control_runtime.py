"""Fail-closed worker-control runtime configuration.

No secret values are logged. Requires a private-interface bind, TLS files,
persistent database locations and an externally provisioned HMAC key.
"""
import ipaddress
import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ControlRuntimeConfig:
    bind_host: str
    port: int
    tls_cert: str
    tls_key: str
    replay_db: str
    stop_db: str
    journal_db: str
    auth_key: bytes


def load_control_runtime_config(env, *, read_bytes=Path.read_bytes):
    if env.get("SWAYZ_CONTROL_ENABLED") != "1":
        raise PermissionError("Control service disabled")
    host = env.get("SWAYZ_CONTROL_BIND", "")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        raise PermissionError("Invalid bind address") from None
    if ip.version != 4 or str(ip) != "10.106.0.3":
        raise PermissionError("Private IPv4 bind required")
    if env.get("SWAYZ_CONTROL_PORT") != "8443":
        raise PermissionError("Unexpected control port")
    paths = {}
    for key in ("SWAYZ_CONTROL_TLS_CERT", "SWAYZ_CONTROL_TLS_KEY",
                "SWAYZ_CONTROL_AUTH_KEY", "SWAYZ_CONTROL_REPLAY_DB",
                "SWAYZ_CONTROL_STOP_DB", "SWAYZ_CONTROL_JOURNAL_DB"):
        value = env.get(key, "")
        if not value or not Path(value).is_absolute():
            raise PermissionError("Absolute control path required")
        paths[key] = value
    for key in ("SWAYZ_CONTROL_TLS_CERT", "SWAYZ_CONTROL_TLS_KEY", "SWAYZ_CONTROL_AUTH_KEY"):
        path = Path(paths[key])
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o022:
            raise PermissionError("Insecure control credential file")
    secret = read_bytes(Path(paths["SWAYZ_CONTROL_AUTH_KEY"]))
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise PermissionError("Invalid control authentication key")
    for key in ("SWAYZ_CONTROL_REPLAY_DB", "SWAYZ_CONTROL_STOP_DB", "SWAYZ_CONTROL_JOURNAL_DB"):
        path = Path(paths[key])
        if path.is_symlink() or not path.parent.is_dir():
            raise PermissionError("Invalid database path")
    return ControlRuntimeConfig(
        host, 8443, paths["SWAYZ_CONTROL_TLS_CERT"], paths["SWAYZ_CONTROL_TLS_KEY"],
        paths["SWAYZ_CONTROL_REPLAY_DB"], paths["SWAYZ_CONTROL_STOP_DB"],
        paths["SWAYZ_CONTROL_JOURNAL_DB"], secret)
