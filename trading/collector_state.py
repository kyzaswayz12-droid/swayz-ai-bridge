"""Persistent read-only collector scheduling state.

Single-process staging controller. No automatic polling or order execution.
"""
import sqlite3
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CollectorState:
    source: str
    pair: str
    last_attempt: Optional[float]
    failures: int
    stopped: bool

class CollectorStateStore:
    def __init__(self,path: str = ":memory:"):
        self.conn=sqlite3.connect(path)
        with self.conn:
            self.conn.execute("""CREATE TABLE IF NOT EXISTS collector_state(
                source TEXT NOT NULL,
                pair TEXT NOT NULL,
                last_attempt REAL,
                failures INTEGER NOT NULL DEFAULT 0,
                stopped INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(source,pair)
            )""")

    def get(self,source: str,pair: str) -> CollectorState:
        row=self.conn.execute(
            "SELECT last_attempt,failures,stopped FROM collector_state WHERE source=? AND pair=?",
            (source,pair)).fetchone()
        return CollectorState(source,pair,row[0],row[1],bool(row[2])) if row else CollectorState(source,pair,None,0,False)

    def record_attempt(self,source: str,pair: str,now: float,min_interval: float) -> bool:
        if min_interval < 10 or now <= 0:
            raise ValueError("Invalid schedule")
        with self.conn:
            state=self.get(source,pair)
            if state.stopped or (state.last_attempt is not None and now-state.last_attempt < min_interval):
                return False
            self.conn.execute(
                "INSERT INTO collector_state(source,pair,last_attempt,failures,stopped) VALUES(?,?,?,0,0) "
                "ON CONFLICT(source,pair) DO UPDATE SET last_attempt=excluded.last_attempt",
                (source,pair,now))
            return True

    def record_result(self,source: str,pair: str,success: bool,max_failures: int=3) -> CollectorState:
        if max_failures < 1:
            raise ValueError("Invalid failure limit")
        with self.conn:
            state=self.get(source,pair)
            if state.last_attempt is None:
                raise ValueError("No prior collection attempt")
            failures=0 if success else state.failures+1
            stopped=state.stopped or failures>=max_failures
            self.conn.execute(
                "UPDATE collector_state SET failures=?,stopped=? WHERE source=? AND pair=?",
                (failures,int(stopped),source,pair))
            return self.get(source,pair)

    def close(self):
        self.conn.close()
