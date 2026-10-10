from trading.dashboard import paper_summary, public_payload
from trading.journal import PaperJournal

def test_dashboard_excludes_private_fields():
    j=PaperJournal()
    j.append("fill:1","fill",{
        "symbol":"BTC/USD","fee":"0.12","account_id":"PRIVATE-ACCOUNT",
        "api_key":"SECRET","balance":"9999","subscriber_id":"user-1"})
    result=public_payload(paper_summary(j))
    assert result["mode"]=="PAPER_SIMULATION"
    assert result["fill_count"]==1
    assert result["performance_verified"] is False
    assert "PRIVATE-ACCOUNT" not in str(result)
    assert "SECRET" not in str(result)
    assert "9999" not in str(result)
    assert "user-1" not in str(result)
    j.close()

def test_empty_dashboard():
    j=PaperJournal()
    result=public_payload(paper_summary(j))
    assert result["fill_count"]==0
    assert result["instruments"]==[]
    j.close()
