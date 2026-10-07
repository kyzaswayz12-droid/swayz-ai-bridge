import hashlib
import hmac
import json
import time
from fastapi.testclient import TestClient
from app import main
from app.core import Store

def signed(payload, secret="test-secret"):
    body=json.dumps(payload).encode()
    ts=str(int(time.time()))
    sig="v0="+hmac.new(secret.encode(),b"v0:"+ts.encode()+b":"+body,hashlib.sha256).hexdigest()
    return {"content":body,"headers":{"x-slack-request-timestamp":ts,"x-slack-signature":sig}}

def test_signature_and_challenge(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET","test-secret")
    client=TestClient(main.app)
    assert client.post("/slack/events",json={}).status_code==401
    response=client.post("/slack/events",**signed({"type":"url_verification","challenge":"abc"}))
    assert response.status_code==200
    assert response.json()=={"challenge":"abc"}

def test_dispatch_and_dedup(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET","test-secret")
    monkeypatch.setenv("ALLOWED_CHANNEL_ID","C1")
    monkeypatch.setenv("ALLOWED_USER_IDS","U1")
    monkeypatch.setenv("DAILY_LIMIT_PER_USER","10")
    monkeypatch.setenv("DAILY_LIMIT_TOTAL","10")
    main.app.state.store=Store()
    calls=[]
    async def fake_process(*args):
        calls.append(args)
    monkeypatch.setattr(main,"process_message",fake_process)
    payload={"type":"event_callback","event":{"type":"message","channel":"C1","user":"U1","ts":"1.1","text":"chatgpt: hello"}}
    with TestClient(main.app) as client:
        assert client.post("/slack/events",**signed(payload)).status_code==200
        assert client.post("/slack/events",**signed(payload)).status_code==200
    assert calls==[("C1","1.1","openai","hello")]
