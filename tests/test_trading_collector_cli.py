from trading.collector_cli import main
import sys
import pytest

def test_cli_rejects_missing_pair(monkeypatch):
    monkeypatch.setattr(sys,"argv",["collector"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code==2
