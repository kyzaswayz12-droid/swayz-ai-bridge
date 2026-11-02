"""HTTP boundary checks: signed Slack events are authorised before queueing.

No worker connections, paid APIs, or production credentials.
"""
import hashlib
import hmac
import json
import time
from fastapi.testclient import TestClient
from app import main
from app.core import Store


def signed(payload):
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = "v0=" + hmac.new(b"test-signing-secret",
        b"v0:" + ts.encode() + b":" + body, hashlib.sha256).hexdigest()
    return {"content": body, "headers": {
        "x-slack-request-timestamp": ts, "x-slack-signature": sig}}


def setup(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("ALLOWED_CHANNEL_ID", "C1")
    monkeypatch.setenv("ALLOWED_USER_IDS", "U1")
    monkeypatch.setenv("SWAYZ_CONTROL_ROUTING_ENABLED", "1")
    monkeypatch.setenv("SWAYZ_REMOTE_CONTROL_ENABLED", "1")
    main.app.state.store = Store()


def payload(user="U1", channel="C1", ts="1.1", text="swayz status"):
    return {"type": "event_callback", "event": {
        "type": "message", "user": user, "channel": channel,
        "ts": ts, "text": text}}


def test_authorised_event_queued_once(monkeypatch):
    setup(monkeypatch)
    calls = []
    async def fake_process(*args):
        calls.append(args)
    monkeypatch.setattr(main, "process_worker_control", fake_process)
    with TestClient(main.app) as client:
        assert client.post("/slack/events", **signed(payload())).status_code == 200
        assert client.post("/slack/events", **signed(payload())).status_code == 200
    assert len(calls) == 1
    assert calls[0][-1].channel == "C1"


def test_unauthorised_user_not_queued(monkeypatch):
    setup(monkeypatch)
    calls = []
    async def fake_process(*args):
        calls.append(args)
    monkeypatch.setattr(main, "process_worker_control", fake_process)
    with TestClient(main.app) as client:
        assert client.post("/slack/events", **signed(payload(user="U2"))).status_code == 200
    assert calls == []


def test_wrong_channel_not_queued(monkeypatch):
    setup(monkeypatch)
    calls = []
    async def fake_process(*args):
        calls.append(args)
    monkeypatch.setattr(main, "process_worker_control", fake_process)
    with TestClient(main.app) as client:
        assert client.post("/slack/events", **signed(payload(channel="C2"))).status_code == 200
    assert calls == []


def test_invalid_slack_signature_rejected(monkeypatch):
    setup(monkeypatch)
    request = signed(payload())
    request["headers"]["x-slack-signature"] = "v0=" + "0" * 64
    with TestClient(main.app) as client:
        assert client.post("/slack/events", **request).status_code == 401


def test_invalid_control_command_not_queued(monkeypatch):
    setup(monkeypatch)
    calls = []
    async def fake_process(*args):
        calls.append(args)
    monkeypatch.setattr(main, "process_worker_control", fake_process)
    with TestClient(main.app) as client:
        assert client.post("/slack/events", **signed(payload(text="swayz enable"))).status_code == 200
    assert calls == []
