"""Read-only verification of executor ledger compatibility.

Legacy tasks and USD reservations are NOT interchangeable with the
authoritative 20-job/day and combined GBP 5/day ledgers. Never silently
create replacement tables or treat the legacy USD 5 cap as GBP 5.
"""
import sqlite3
from pathlib import Path

EXPECTED = {
    "job": {"admitted_jobs": {"job_id", "day_utc"}},
    "budget": {"gbp_reservations": {
        "request_id", "provider", "day_utc", "reserved_gbp",
        "status", "actual_gbp"}},
}


def verify_executor_ledger(path: str, kind: str) -> None:
    if kind not in EXPECTED:
        raise ValueError("Unknown ledger type")
    p = Path(path)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise PermissionError("Required executor ledger unavailable")
    try:
        with sqlite3.connect(p.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
            for table, required in EXPECTED[kind].items():
                columns = {row[1] for row in db.execute(
                    "PRAGMA table_info(" + table + ")")}
                if not required.issubset(columns):
                    raise PermissionError(
                        "Incompatible " + kind + " ledger: expected " + table +
                        "; legacy databases require reconciliation, not auto-migration")
    except sqlite3.Error as exc:
        raise PermissionError("Executor ledger unreadable") from exc
