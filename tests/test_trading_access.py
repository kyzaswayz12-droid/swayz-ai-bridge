from trading.entitlements import SubscriberRegistry
from trading.access import authorised_recipients

def test_premium_targeting_excludes_free_expired_and_revoked():
    r=SubscriberRegistry()
    r.grant("tg:1","premium",200)
    r.grant("tg:2","free",200)
    r.grant("tg:3","premium",50)
    r.grant("tg:4","premium",200)
    r.revoke("tg:4")
    result=authorised_recipients(r,["tg:1","tg:2","tg:3","tg:4","tg:1","missing"],"premium",100)
    assert result==["tg:1"]
    r.close()

def test_free_access_includes_active_premium():
    r=SubscriberRegistry()
    r.grant("dc:1","premium",200)
    r.grant("dc:2","free",200)
    assert authorised_recipients(r,["dc:1","dc:2"],"free",100)==["dc:1","dc:2"]
    r.close()
