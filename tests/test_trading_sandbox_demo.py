import asyncio
from trading.sandbox_demo import run_sandbox_demo

def test_sandbox_publication_end_to_end():
    result=asyncio.run(run_sandbox_demo())
    assert result["mode"]=="sandbox"
    assert result["publication_status"]=="sent"
    assert result["provider"]=="telegram"
    assert result["real_network_requests"]==0
