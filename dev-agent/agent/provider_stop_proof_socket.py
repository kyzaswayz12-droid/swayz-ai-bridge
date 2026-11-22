"""Narrow, root-controlled local stop-proof socket for provider-only jobs.

No HTTP, Docker, GitHub, signing of executor jobs or emergency-stop release.
Run as a separately reviewed root service, with a DEDICATED provider-grant
Ed25519 key. A request from swayzdev receives only a short-lived stop proof
after verifying the original signed grant and BOTH GBP reservations.
Nothing starts on import; this is not installed/enabled by GitHub CI.
"""
import grp
import hashlib
import json
import os
import socket
import sqlite3
import struct
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .split_provider_authority import _canonical, _clock, JOB_RE, MODELS, TASK, MAX_USD
from .split_provider_transport import issue_stop_proof

MAX_REQUEST = 2048
MAX_RESPONSE = 4096


def _read_regular(path, limit):
    p=Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file() or p.stat().st_size > limit:
        raise PermissionError("Protected file missing or unsafe")
    return p.read_bytes()


def _root_grant_check(*, job_id, grant_digest, grant_directory, signing_key,
                      budget_db, now):
    if not isinstance(job_id, str) or not JOB_RE.fullmatch(job_id):
        raise PermissionError("Job identity invalid")
    if not isinstance(grant_digest, str) or len(grant_digest) != 64:
        raise PermissionError("Grant digest invalid")
    p=Path(grant_directory)
    if not p.is_absolute() or p.is_symlink() or not p.is_dir() or p.stat().st_uid != 0 or p.stat().st_mode & 0o077:
        raise PermissionError("Root grant directory unprotected")
    data=_read_regular(p/(job_id+".grant.json"),16384)
    if hashlib.sha256(data).hexdigest() != grant_digest:
        raise PermissionError("Grant digest mismatch")
    try:
        document=json.loads(data)
        if set(document) != {"payload","signature"}:
            raise ValueError("Grant structure invalid")
        payload=document["payload"]
        signing_key.public_key().verify(
            bytes.fromhex(document["signature"]),_canonical(payload))
        issued=_clock(datetime.fromisoformat(payload["issued_utc"]))
        expiry=_clock(datetime.fromisoformat(payload["expires_utc"]))
        now=_clock(now)
        if (payload["job_id"] != job_id or payload["purpose"] != "swayz-provider-only-proposal"
                or payload["models"] != list(MODELS)
                or payload["task_sha256"] != hashlib.sha256(TASK.encode()).hexdigest()
                or payload["request_ids"] != [job_id+"-openai",job_id+"-anthropic"]
                or not issued <= now <= expiry
                or payload["docker_authorised"] is not False
                or payload["github_writes_authorised"] is not False
                or payload["live_trading_authorised"] is not False
                or payload["retries"] != 0
                or Decimal(payload["reserved_usd"]) > MAX_USD):
            raise ValueError("Grant outside its scope or expired")
    except (ValueError, TypeError, KeyError, InvalidSignature, AttributeError) as exc:
        raise PermissionError("Original grant invalid") from exc
    b=Path(budget_db)
    if not b.is_absolute() or b.is_symlink() or not b.is_file():
        raise PermissionError("Budget ledger unavailable")
    with sqlite3.connect(b.as_uri()+"?mode=ro",uri=True,timeout=5) as db:
        rows=db.execute(
            "SELECT request_id,provider,day_utc,reserved_gbp,status,actual_gbp "
            "FROM gbp_reservations WHERE request_id IN (?,?)",
            tuple(payload["request_ids"])).fetchall()
    if len(rows) != 2:
        raise PermissionError("Both durable provider reservations required")
    reservations={row[0]: row for row in rows}
    if set(reservations) != set(payload["request_ids"]):
        raise PermissionError("Mismatched request reservations")
    for request_id,provider in zip(payload["request_ids"],("openai","anthropic")):
        row=reservations[request_id]
        if row[1] != provider or row[2] != issued.date().isoformat() or row[4] != "reserved" or row[5] is not None:
            raise PermissionError("Provider reservation not active")
    if sum(Decimal(row[3]) for row in rows) != Decimal(payload["reserved_gbp"]):
        raise PermissionError("Reserved GBP amounts mismatch")
    return data


def _answer(*, request, peer_uid, allowed_uid, root_grants, signing_key,
            budget_db, stop_db, now):
    """Internal helper called only after SO_PEERCRED verification."""
    if type(peer_uid) is not int or peer_uid != allowed_uid:
        raise PermissionError("Unapproved peer account")
    if not isinstance(request, dict) or set(request) != {"job_id","phase","grant_sha256"}:
        raise PermissionError("Unexpected root proof request")
    phase=request["phase"]
    if phase not in ("openai","anthropic"):
        raise PermissionError("Unapproved provider phase")
    data=_root_grant_check(
        job_id=request["job_id"],grant_digest=request["grant_sha256"],
        grant_directory=root_grants,signing_key=signing_key,
        budget_db=budget_db,now=now)
    return issue_stop_proof(job_id=request["job_id"],phase=phase,
                            grant_bytes=data,stop_db=stop_db,
                            signing_key=signing_key,now=now)


def request_stop_proof_socket(*, socket_path, phase, grant_bytes, job_id):
    """swayzdev asks the root-only service for one fresh stop proof."""
    if not isinstance(grant_bytes, bytes) or len(grant_bytes) > 16384:
        raise PermissionError("Invalid grant")
    p=Path(socket_path)
    if not p.is_absolute() or p.is_symlink():
        raise PermissionError("Socket path invalid")
    request=_canonical({
        "job_id":job_id,"phase":phase,
        "grant_sha256":hashlib.sha256(grant_bytes).hexdigest()})
    if len(request)>MAX_REQUEST:
        raise PermissionError("Oversized proof request")
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.settimeout(3)
        s.connect(str(p))
        s.sendall(request+b"\n")
        response=b""
        while not response.endswith(b"\n") and len(response)<=MAX_RESPONSE:
            chunk=s.recv(1024)
            if not chunk:
                break
            response+=chunk
    if len(response)>MAX_RESPONSE or not response.endswith(b"\n"):
        raise PermissionError("Incomplete privileged proof")
    return response[:-1]


def serve_one_peer(*, connection, allowed_uid, root_grants,
                   signing_key, budget_db, stop_db, now=None):
    """One authenticated SO_PEERCRED request; caller owns socket lifecycle."""
    if os.geteuid()!=0 or not isinstance(signing_key,Ed25519PrivateKey):
        raise PermissionError("Root-only proof service")
    uid=struct.unpack("3i",connection.getsockopt(
        socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize("3i")))[1]
    if uid != allowed_uid:
        raise PermissionError("Socket peer not swayzdev")
    data=b""
    connection.settimeout(3)
    while not data.endswith(b"\n") and len(data)<=MAX_REQUEST:
        part=connection.recv(512)
        if not part:
            break
        data+=part
    if len(data)>MAX_REQUEST or not data.endswith(b"\n"):
        raise PermissionError("Invalid proof request framing")
    request=json.loads(data[:-1])
    reply=_answer(request=request,peer_uid=uid,allowed_uid=allowed_uid,
                  root_grants=root_grants,signing_key=signing_key,
                  budget_db=budget_db,stop_db=stop_db,
                  now=now or datetime.now(timezone.utc))
    connection.sendall(reply+b"\n")
    return {"state":"stop_proof_issued","provider_calls":0}
