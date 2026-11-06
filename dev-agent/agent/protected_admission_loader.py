"""Root-owned metadata loader for the existing protected signing receiver.

No network listener, AI-provided path, or signing-key exposure. Metadata is
loaded exclusively from a fixed trusted directory by job ID. The signer
performs its own independent admission, snapshot and policy verification.
"""
import json
import os
import re
import stat
from pathlib import Path

_JOB = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_FIELDS = {"job_id", "commit_sha", "proposal_sha256", "manifest_sha256",
           "snapshot", "snapshot_root", "expected_hashes", "image_digest",
           "approved_images", "queue_db", "job_db", "journal_db",
           "stop_db", "signing_key_file", "request_directory"}


def load_protected_job(job_id, *, metadata_directory="/var/lib/swayz-executor/admission-metadata"):
    if os.geteuid() != 0 or not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise PermissionError("Privileged valid job identity required")
    directory = Path(metadata_directory)
    if not directory.is_absolute() or directory.is_symlink():
        raise PermissionError("Protected metadata directory required")
    st = directory.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        raise PermissionError("Metadata directory must be root-owned and private")
    path = directory / (job_id + ".json")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        fst = os.fstat(fd)
        if (not stat.S_ISREG(fst.st_mode) or fst.st_uid != 0
                or fst.st_mode & 0o077 or fst.st_nlink != 1
                or fst.st_size > 65536):
            raise PermissionError("Unprotected metadata file")
        with os.fdopen(fd, "rb", closefd=False) as f:
            raw = f.read(65537)
        if len(raw) > 65536:
            raise PermissionError("Oversized metadata")
        doc = json.loads(raw)
    finally:
        os.close(fd)
    if not isinstance(doc, dict) or set(doc) != _FIELDS or doc["job_id"] != job_id:
        raise PermissionError("Invalid protected admission metadata")
    if not isinstance(doc["approved_images"], list) or not doc["approved_images"]:
        raise PermissionError("Missing approved images")
    if any(not isinstance(v, str) for v in doc["approved_images"]):
        raise PermissionError("Invalid approved image list")
    doc["approved_images"] = frozenset(doc["approved_images"])
    return doc
