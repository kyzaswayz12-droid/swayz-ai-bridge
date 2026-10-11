"""Usage-based cost calculation without asserting billing verification.

Model rates are supplied from an independently verified rate card.
A token estimate is not a provider invoice: this function deliberately
does not call BudgetStore.settle().
"""
from dataclasses import dataclass
from decimal import Decimal
from .cost_estimates import RateCard, estimated_cost

@dataclass(frozen=True)
class UsageCost:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_usd: Decimal
    billing_verified: bool = False

def calculate_usage_cost(provider: str, card: RateCard, *,
                         model: str, input_tokens: int,
                         output_tokens: int) -> UsageCost:
    if provider not in ("openai","anthropic") or model != card.model:
        raise ValueError("Provider or model mismatch")
    return UsageCost(provider,model,input_tokens,output_tokens,
                     estimated_cost(card,input_tokens,output_tokens))
