from trading.entitlements import SubscriberRegistry

def test_premium_expiry_and_revoke(tmp_path):
    p=str(tmp_path/"subscribers.db")
    r=SubscriberRegistry(p)
    r.grant("telegram:123","premium",2000)
    assert r.eligible("telegram:123","premium",now=1999)
    assert not r.eligible("telegram:123","premium",now=2000)
    r.close()
    r=SubscriberRegistry(p)
    assert r.eligible("telegram:123","free",now=1999)
    assert r.revoke("telegram:123")
    assert not r.eligible("telegram:123","premium",now=1999)
    r.close()

def test_free_cannot_access_premium():
    r=SubscriberRegistry()
    r.grant("discord:1","free",5000)
    assert r.eligible("discord:1","free",now=1000)
    assert not r.eligible("discord:1","premium",now=1000)
    assert not r.eligible("missing","free",now=1000)
    r.close()
