"""Reference rate cards verified against official public standard text pricing.

Not an owner-approved billing record. Used for estimates only. Recheck
pricing, availability and special billing conditions before paid execution.
"""
from decimal import Decimal
from .cost_estimates import RateCard

REFERENCE_RATES={
    ("openai","gpt-5-mini"):RateCard("gpt-5-mini",Decimal("0.25"),Decimal("2.00")),
    ("anthropic","claude-haiku-4-5-20251001"):RateCard(
        "claude-haiku-4-5-20251001",Decimal("1.00"),Decimal("5.00")),
}

SOURCES={
    ("openai","gpt-5-mini"):"https://developers.openai.com/api/docs/models/gpt-5-mini",
    ("anthropic","claude-haiku-4-5-20251001"):"https://www.anthropic.com/claude/haiku",
}

def reference_rate(provider: str, model: str) -> RateCard:
    try:
        return REFERENCE_RATES[(provider,model)]
    except KeyError:
        raise ValueError("Unknown reference rate; fail closed") from None
