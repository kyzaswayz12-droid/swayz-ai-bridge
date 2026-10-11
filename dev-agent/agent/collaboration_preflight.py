"""Fail-closed preflight for one-shot development collaboration.

Does not contact providers, read credentials, mutate the ledger, or start jobs.
"""
from pathlib import Path
from .rate_card_loader import load_rate_card
from .collaboration_cost_preview import preview_task

def preflight(task, *, openai_card: Path, claude_card: Path,
              openai_model="gpt-5-mini",
              claude_model="claude-haiku-4-5-20251001"):
    a=load_rate_card(openai_card,"openai",openai_model)
    b=load_rate_card(claude_card,"anthropic",claude_model)
    # Current preview uses reference rates; refuse any rate mismatch.
    from .reference_rates import reference_rate
    if a!=reference_rate("openai",openai_model) or b!=reference_rate("anthropic",claude_model):
        raise PermissionError("Verified rate cards disagree with configured reference rates")
    result=preview_task(task,openai_model=openai_model,claude_model=claude_model)
    if result.total_reservation_usd<=0 or result.total_reservation_usd>1:
        raise PermissionError("Collaboration cost preview outside permitted staging range")
    return {"state":"preflight_passed","provider_calls":0,
            "openai_reserved_usd":str(result.openai_reservation_usd),
            "claude_reserved_usd":str(result.claude_reservation_usd),
            "total_reserved_usd":str(result.total_reservation_usd),
            "billing_verified":False}
