"""Framework-free Slack routing, access control and SQLite counters."""
import hashlib
import hmac
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Mapping, Optional, Union

MAX_PROMPT_CHARS = 4000
MAX_REPLY_CHARS = 3500
SIGNATURE_MAX_AGE_SECONDS = 300
DEFAULT_PER_USER_DAILY_LIMIT = 0
DEFAULT_TOTAL_DAILY_LIMIT = 0
DEDUP_RETENTION_SECONDS = 7 * 24 * 3600
USAGE_RETENTION_DAYS = 30

GENERIC_ERROR_TEXT = "Sorry, something went wrong handling that request. Please try again later."
EMPTY_PROMPT_TEXT = "Please put your question after the prefix, e.g. `chatgpt: your question` or `claude: your question`."
TOO_LONG_TEXT = f"That message is too long (maximum {MAX_PROMPT_CHARS} characters)."
LIMIT_TEXTS = {
    "user_limit": "You have reached your daily request limit. Please try again tomorrow (UTC).",
    "total_limit": "The daily request limit for this channel has been reached. Please try again tomorrow (UTC).",
    "disabled": "AI requests are disabled until the project owner enables them.",
}
_COMMAND_RE = re.compile(r"^\s*(chatgpt|claude)\s*:\s*(.*)$", re.IGNORECASE | re.DOTALL)
_PROVIDERS = {"chatgpt": "openai", "claude": "anthropic"}


class MissingConfig(RuntimeError):
    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


def valid_signature(body: bytes, timestamp: str, signature: str, secret: str, now: Optional[float] = None) -> bool:
    if not (secret and timestamp and signature):
        return False
    try:
        if abs((time.time() if now is None else now) - int(timestamp)) > SIGNATURE_MAX_AGE_SECONDS:
            return False
    except ValueError:
        return False
    digest = hmac.new(secret.encode(), b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("v0=" + digest, signature)


@dataclass(frozen=True)
class Command:
    provider: str
    prompt: str
    problem: Optional[str] = None


def parse_command(text: str) -> Optional[Command]:
    match = _COMMAND_RE.match(text or "")
    if not match:
        return None
    provider = _PROVIDERS[match.group(1).lower()]
    prompt = match.group(2).strip()
    if not prompt:
        return Command(provider, "", "empty")
    if len(prompt) > MAX_PROMPT_CHARS:
        return Command(provider, "", "too_long")
    return Command(provider, prompt)


def _positive_int(raw: Optional[str], default: int) -> int:
    try:
        value = int(raw) if raw is not None and raw.strip() else default
    except ValueError:
        return default
    return value if value >= 0 else default


@dataclass(frozen=True)
class Settings:
    allowed_channel: str
    allowed_users: frozenset
    per_user_limit: int
    total_limit: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "Settings":
        users = frozenset(part for part in re.split(r"[,\s]+", environ.get("ALLOWED_USER_IDS", "")) if part)
        return cls(
            allowed_channel=environ.get("ALLOWED_CHANNEL_ID", "").strip(),
            allowed_users=users,
            per_user_limit=_positive_int(environ.get("DAILY_LIMIT_PER_USER"), DEFAULT_PER_USER_DAILY_LIMIT),
            total_limit=_positive_int(environ.get("DAILY_LIMIT_TOTAL"), DEFAULT_TOTAL_DAILY_LIMIT),
        )


class Store:
    """Single-process SQLite store; use a persistent volume for deployed state."""

    def __init__(self, path: str = ":memory:", retention_seconds: int = DEDUP_RETENTION_SECONDS):
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        self._retention = retention_seconds
        with self._lock:
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("CREATE TABLE IF NOT EXISTS seen_messages (key TEXT PRIMARY KEY, seen_at INTEGER NOT NULL)")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS usage ("
                "day TEXT NOT NULL, user_id TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY (day, user_id))"
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def claim_message(self, channel: str, ts: str, now: float) -> bool:
        key = f"{channel}:{ts}"
        with self._lock:
            self._conn.execute("DELETE FROM seen_messages WHERE seen_at < ?", (int(now - self._retention),))
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO seen_messages (key, seen_at) VALUES (?, ?)", (key, int(now))
            )
            return cursor.rowcount == 1

    def try_consume(self, user_id: str, now: float, per_user_limit: int, total_limit: int) -> Optional[str]:
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        oldest_day = time.strftime("%Y-%m-%d", time.gmtime(now - USAGE_RETENTION_DAYS * 86400))
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute("DELETE FROM usage WHERE day < ?", (oldest_day,))
                total, mine = self._conn.execute(
                    "SELECT COALESCE(SUM(count), 0), COALESCE(SUM(CASE WHEN user_id = ? THEN count ELSE 0 END), 0) "
                    "FROM usage WHERE day = ?", (user_id, day)
                ).fetchone()
                if mine >= per_user_limit:
                    reason = "user_limit"
                elif total >= total_limit:
                    reason = "total_limit"
                else:
                    reason = None
                    self._conn.execute(
                        "INSERT INTO usage (day, user_id, count) VALUES (?, ?, 1) "
                        "ON CONFLICT(day, user_id) DO UPDATE SET count = count + 1", (day, user_id)
                    )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return reason


@dataclass(frozen=True)
class Challenge:
    value: str


@dataclass(frozen=True)
class Ignore:
    reason: str


@dataclass(frozen=True)
class Reply:
    channel: str
    thread_ts: str
    text: str


@dataclass(frozen=True)
class CallModel:
    channel: str
    thread_ts: str
    provider: str
    prompt: str


Action = Union[Challenge, Ignore, Reply, CallModel]


def handle_event(payload: object, settings: Settings, store: Store, now: float) -> Action:
    """Decide how to handle a signature-verified Slack event."""
    if not isinstance(payload, dict):
        return Ignore("bad_payload")
    kind = payload.get("type")
    if kind == "url_verification":
        return Challenge(str(payload.get("challenge", "")))
    event = payload.get("event")
    if kind != "event_callback" or not isinstance(event, dict) or event.get("type") != "message":
        return Ignore("not_a_message")
    user = event.get("user")
    if event.get("bot_id") or event.get("subtype") or not isinstance(user, str) or not user:
        return Ignore("bot_or_subtype")
    channel, ts = event.get("channel"), event.get("ts")
    if not settings.allowed_channel or channel != settings.allowed_channel:
        return Ignore("channel_not_allowed")
    if user not in settings.allowed_users:
        return Ignore("user_not_allowed")
    command = parse_command(event.get("text") if isinstance(event.get("text"), str) else "")
    if command is None:
        return Ignore("no_command")
    if not isinstance(ts, str) or not ts:
        return Ignore("no_timestamp")
    if not store.claim_message(channel, ts, now):
        return Ignore("duplicate")
    thread_ts = event.get("thread_ts") if isinstance(event.get("thread_ts"), str) and event.get("thread_ts") else ts
    if command.problem == "empty":
        return Reply(channel, thread_ts, EMPTY_PROMPT_TEXT)
    if command.problem == "too_long":
        return Reply(channel, thread_ts, TOO_LONG_TEXT)
    if settings.per_user_limit == 0 or settings.total_limit == 0:
        return Reply(channel, thread_ts, LIMIT_TEXTS["disabled"])
    limit_hit = store.try_consume(user, now, settings.per_user_limit, settings.total_limit)
    if limit_hit:
        return Reply(channel, thread_ts, LIMIT_TEXTS[limit_hit])
    return CallModel(channel, thread_ts, command.provider, command.prompt)
