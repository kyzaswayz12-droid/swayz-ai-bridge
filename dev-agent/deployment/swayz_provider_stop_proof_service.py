"""Disabled-by-default dedicated root stop-proof service entrypoint.

Requires separate root-only Ed25519 provider-grant key and pre-provisioned
root:swayzdev 0750 socket directory. Nothing is enabled or installed by CI.
NO executor key, Docker, provider API, GitHub or trading access is used.
"""
import grp
import os
import socket
import stat
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent.provider_stop_proof_socket import serve_one_peer

BASE = Path("/run/swayz-provider-proofs")
SOCKET = BASE / "stop-proof.sock"
KEY = Path("/etc/swayz-collaboration/provider-grant-signing.key")
ROOT_GRANTS = "/var/lib/swayz-provider-grants"
BUDGET = "/var/lib/swayz-executor/budget.sqlite3"
STOP = "/var/lib/swayzcontrol/state/stop.db"


def run_service():
    if os.geteuid() != 0:
        raise PermissionError("Root-owned standalone proof service required")
    worker_gid = grp.getgrnam("swayzdev").gr_gid
    worker_uid = __import__("pwd").getpwnam("swayzdev").pw_uid
    info = BASE.stat()
    if (BASE.is_symlink() or not BASE.is_dir() or info.st_uid != 0
            or info.st_gid != worker_gid or stat.S_IMODE(info.st_mode) != 0o750):
        raise PermissionError("Protected socket directory missing")
    if SOCKET.exists() or SOCKET.is_symlink():
        raise PermissionError("Stale proof socket; operator reconciliation required")
    info = KEY.stat()
    if (KEY.is_symlink() or not KEY.is_file() or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size != 32):
        raise PermissionError("Dedicated provider signing key not provisioned safely")
    key = Ed25519PrivateKey.from_private_bytes(KEY.read_bytes())
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.settimeout(5)
        old_umask = os.umask(0o077)
        try:
            server.bind(str(SOCKET))
            os.chown(SOCKET, 0, worker_gid)
            os.chmod(SOCKET, 0o660)
        finally:
            os.umask(old_umask)
        server.listen(4)
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            with conn:
                try:
                    serve_one_peer(
                        connection=conn, allowed_uid=worker_uid,
                        root_grants=ROOT_GRANTS, signing_key=key,
                        budget_db=BUDGET, stop_db=STOP)
                except Exception:
                    # Fail-closed: malformed requests are not granted proofs.
                    # No error text or secrets are sent to the peer.
                    pass


if __name__ == "__main__":
    run_service()
