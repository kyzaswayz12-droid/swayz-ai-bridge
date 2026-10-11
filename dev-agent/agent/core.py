"""Fail-closed task coordinator for the isolated development agent."""
from dataclasses import dataclass
from enum import Enum
import sqlite3
import time
import re

SHA = re.compile(r"^[a-f0-9]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

class State(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    CODE_READY = "code_ready"
    REVIEW_REQUIRED = "review_required"
    APPROVAL_REQUIRED = "approval_required"
    COMPLETE = "complete"
    BLOCKED = "blocked"

@dataclass(frozen=True)
class Policy:
    repository: str
    branch_prefix: str = "agent/"
    max_daily_model_calls: int = 20
    max_daily_budget_usd: float = 5.0
    max_iterations_per_task: int = 3
    enable_model_calls: bool = False
    enable_git_writes: bool = False
    enable_deployment: bool = False
    enable_live_trading: bool = False

    def __post_init__(self):
        if not REPO.fullmatch(self.repository):
            raise ValueError("Invalid repository")
        if self.branch_prefix != "agent/":
            raise ValueError("Agent branch restriction cannot be changed in staging")
        if not 1 <= self.max_daily_model_calls <= 100:
            raise ValueError("Invalid call limit")
        if not 0 < self.max_daily_budget_usd <= 100:
            raise ValueError("Invalid budget")
        if not 1 <= self.max_iterations_per_task <= 5:
            raise ValueError("Invalid iteration cap")
        if any((self.enable_model_calls, self.enable_git_writes,
                self.enable_deployment, self.enable_live_trading)):
            raise ValueError("Staging policy forbids external actions")

class TaskStore:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS tasks(
            task_id TEXT PRIMARY KEY, title TEXT NOT NULL, state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, claimed_at INTEGER,
            updated_at INTEGER NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS audit(
            seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
            old_state TEXT, new_state TEXT NOT NULL, event_at INTEGER NOT NULL)""")

    def enqueue(self, task_id, title):
        if not task_id or not title or len(task_id) > 128 or len(title) > 240:
            raise ValueError("Invalid task")
        now = int(time.time())
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result = self.db.execute("INSERT OR IGNORE INTO tasks(task_id,title,state,updated_at) VALUES(?,?,?,?)",
                                     (task_id,title,State.PENDING.value,now))
            if result.rowcount:
                self.db.execute("INSERT INTO audit(task_id,old_state,new_state,event_at) VALUES(?,?,?,?)",
                                (task_id,None,State.PENDING.value,now))
            self.db.execute("COMMIT")
            return bool(result.rowcount)
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def claim_next(self, max_attempts=3):
        if not 1 <= max_attempts <= 5:
            raise ValueError("Invalid attempt limit")
        now = int(time.time())
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT task_id,title FROM tasks WHERE state=? AND attempts<? ORDER BY updated_at,task_id LIMIT 1",
                                  (State.PENDING.value,max_attempts)).fetchone()
            if row:
                self.db.execute("UPDATE tasks SET state=?,attempts=attempts+1,claimed_at=?,updated_at=? WHERE task_id=?",
                                (State.CLAIMED.value,now,now,row[0]))
                self.db.execute("INSERT INTO audit(task_id,old_state,new_state,event_at) VALUES(?,?,?,?)",
                                (row[0],State.PENDING.value,State.CLAIMED.value,now))
            self.db.execute("COMMIT")
            return row
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def transition(self, task_id, expected, target):
        allowed = {
            State.CLAIMED: {State.CODE_READY, State.BLOCKED},
            State.CODE_READY: {State.REVIEW_REQUIRED, State.BLOCKED},
            State.REVIEW_REQUIRED: {State.APPROVAL_REQUIRED, State.BLOCKED},
            State.APPROVAL_REQUIRED: {State.COMPLETE, State.BLOCKED},
        }
        if target not in allowed.get(expected,set()):
            raise ValueError("Forbidden state transition")
        now=int(time.time())
        self.db.execute("BEGIN IMMEDIATE")
        try:
            cur=self.db.execute("UPDATE tasks SET state=?,updated_at=? WHERE task_id=? AND state=?",
                                (target.value,now,task_id,expected.value))
            if cur.rowcount!=1:
                raise ValueError("Stale or unknown task")
            self.db.execute("INSERT INTO audit(task_id,old_state,new_state,event_at) VALUES(?,?,?,?)",
                            (task_id,expected.value,target.value,now))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def status(self):
        return dict(self.db.execute("SELECT state,COUNT(*) FROM tasks GROUP BY state"))

    def close(self):
        self.db.close()
