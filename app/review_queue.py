"""Persistent GitHub review event queue, disabled by default.

Does not invoke Claude; approval and bounded diff retrieval are separate stages.
"""
import sqlite3
import time
from .github_review import ReviewCandidate

class ReviewQueue:
    def __init__(self,path: str=":memory:"):
        self.conn=sqlite3.connect(path)
        with self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS review_queue(
                repository TEXT NOT NULL,
                pull_number INTEGER NOT NULL,
                head_sha TEXT NOT NULL,
                base_ref TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','approved','reviewed','rejected')),
                created_at INTEGER NOT NULL,
                PRIMARY KEY(repository,pull_number,head_sha)
            )""")

    def enqueue(self,candidate: ReviewCandidate) -> bool:
        with self.conn:
            cursor=self.conn.execute(
                "INSERT OR IGNORE INTO review_queue VALUES(?,?,?,?,?,?)",
                (candidate.repository,candidate.pull_number,candidate.head_sha,
                 candidate.base_ref,"pending",int(time.time())))
            return cursor.rowcount==1

    def approve(self,repository: str,pull_number: int,head_sha: str) -> bool:
        with self.conn:
            cursor=self.conn.execute(
                "UPDATE review_queue SET status='approved' WHERE repository=? "
                "AND pull_number=? AND head_sha=? AND status='pending'",
                (repository,pull_number,head_sha))
            return cursor.rowcount==1

    def status(self,repository: str,pull_number: int,head_sha: str) -> str | None:
        row=self.conn.execute(
            "SELECT status FROM review_queue WHERE repository=? AND pull_number=? AND head_sha=?",
            (repository,pull_number,head_sha)).fetchone()
        return row[0] if row else None

    def close(self):
        self.conn.close()
