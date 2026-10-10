from fastapi.testclient import TestClient
from trading.dashboard_api import create_dashboard_app
from trading.journal import PaperJournal

def test_dashboard_api_returns_paper_only(tmp_path):
    path=str(tmp_path/"paper.sqlite3")
    j=PaperJournal(path)
    j.append("fill:1","fill",{"symbol":"BTC/USD","fee":"0.2","api_key":"SECRET"})
    j.close()
    client=TestClient(create_dashboard_app(path))
    response=client.get("/api/paper-summary")
    assert response.status_code==200
    data=response.json()
    assert data["mode"]=="PAPER_SIMULATION"
    assert data["performance_verified"] is False
    assert data["fill_count"]==1
    assert "SECRET" not in response.text

def test_no_trading_endpoint(tmp_path):
    client=TestClient(create_dashboard_app(str(tmp_path/"paper.sqlite3")))
    assert client.post("/api/orders",json={}).status_code==404
