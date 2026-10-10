from trading.collector_state import CollectorStateStore

def test_state_survives_restart(tmp_path):
    path=str(tmp_path/"collector.db")
    s=CollectorStateStore(path)
    assert s.record_attempt("kraken","XBTUSD",100,60)
    assert not s.record_attempt("kraken","XBTUSD",110,60)
    s.record_result("kraken","XBTUSD",False,max_failures=2)
    s.close()
    s=CollectorStateStore(path)
    assert s.get("kraken","XBTUSD").failures==1
    assert s.record_attempt("kraken","XBTUSD",170,60)
    state=s.record_result("kraken","XBTUSD",False,max_failures=2)
    assert state.stopped
    assert not s.record_attempt("kraken","XBTUSD",300,60)
    s.close()

def test_success_resets_failure_counter():
    s=CollectorStateStore()
    s.record_attempt("kraken","ETHUSD",100,60)
    s.record_result("kraken","ETHUSD",False)
    s.record_attempt("kraken","ETHUSD",200,60)
    assert s.record_result("kraken","ETHUSD",True).failures==0
    s.close()
