import hashlib
import hmac
from app.main import route, valid_signature


def test_explicit_routing():
    assert route("@chatgpt hello") == ("openai", "hello")
    assert route("@claude hello") == ("anthropic", "hello")
    assert route("hello") is None
    assert route("@claude ") is None


def test_signature_and_replay_window():
    body = b'{"type":"event_callback"}'
    ts = "1000"
    sig = "v0=" + hmac.new(b"secret", b"v0:1000:" + body, hashlib.sha256).hexdigest()
    assert valid_signature(body, ts, sig, "secret", now=1001)
    assert not valid_signature(body + b"x", ts, sig, "secret", now=1001)
    assert not valid_signature(body, ts, sig, "secret", now=1400)
