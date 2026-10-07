import tempfile
from pathlib import Path
from app.core import Settings, Store, handle_event, CallModel, Ignore, Reply, LIMIT_TEXTS

def event(text="chatgpt: hello", user="U1", ts="1.1", channel="C1", **extra):
    e = {"type":"message","text":text,"user":user,"ts":ts,"channel":channel}
    e.update(extra)
    return {"type":"event_callback","event":e}

def settings(**changes):
    d = dict(allowed_channel="C1",allowed_users=frozenset({"U1"}),per_user_limit=2,total_limit=3)
    d.update(changes)
    return Settings(**d)

def test_allowlist_and_channel_fail_closed():
    assert isinstance(handle_event(event(),settings(allowed_users=frozenset()),Store(),1000),Ignore)
    assert isinstance(handle_event(event(channel="C2"),settings(),Store(),1000),Ignore)

def test_dedup_and_limits():
    s=Store()
    cfg=settings()
    assert isinstance(handle_event(event(ts="1.1"),cfg,s,1000),CallModel)
    assert handle_event(event(ts="1.1"),cfg,s,1000)==Ignore("duplicate")
    assert isinstance(handle_event(event(ts="1.2"),cfg,s,1000),CallModel)
    assert handle_event(event(ts="1.3"),cfg,s,1000)==Reply("C1","1.3",LIMIT_TEXTS["user_limit"])

def test_persistence():
    with tempfile.TemporaryDirectory() as d:
        p=str(Path(d)/"state.db")
        s=Store(p)
        assert s.claim_message("C1","1.1",1000)
        s.close()
        s=Store(p)
        assert not s.claim_message("C1","1.1",1001)
        s.close()

def test_settings():
    s=Settings.from_env({"ALLOWED_USER_IDS":"U1,U2","ALLOWED_CHANNEL_ID":"C1","DAILY_LIMIT_TOTAL":"0"})
    assert s.allowed_users==frozenset({"U1","U2"})
    assert s.total_limit==0
