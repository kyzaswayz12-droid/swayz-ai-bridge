import asyncio
import pytest
from trading.team import collaborate

def test_two_model_calls_in_order():
    calls = []
    async def fake(provider, prompt):
        calls.append(provider)
        return "Plan" if provider == "openai" else "Review"
    result = asyncio.run(collaborate("Research BTC strategy", fake))
    assert calls == ["openai", "anthropic"]
    assert result.status == "review_required"
    assert result.proposal == "Plan" and result.review == "Review"

def test_invalid_goal_no_calls():
    calls = []
    async def fake(provider, prompt):
        calls.append(provider)
        return "unused"
    with pytest.raises(ValueError):
        asyncio.run(collaborate(" ", fake))
    assert calls == []

def test_failed_review_is_not_success():
    async def fake(provider, prompt):
        if provider == "anthropic":
            raise RuntimeError("provider unavailable")
        return "Plan"
    with pytest.raises(RuntimeError):
        asyncio.run(collaborate("Review an idea", fake))
