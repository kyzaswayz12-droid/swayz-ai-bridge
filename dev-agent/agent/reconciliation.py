"""Read-only reconciliation candidates, never auto-settles reservations.

Token-cost estimates are informational. Provider-billed charges must be
independently matched to request IDs before BudgetStore.settle() is used.
"""
from dataclasses import dataclass
from decimal import Decimal
from .usage_cost import UsageCost

@dataclass(frozen=True)
class ReconciliationCandidate:
    request_id: str
    reserved_usd: Decimal
    estimated_usd: Decimal
    releasable_usd: Decimal
    status: str

def propose_reconciliation(request_id: str, reserved_usd: Decimal,
                           usage: UsageCost) -> ReconciliationCandidate:
    if not isinstance(request_id,str) or not request_id.strip() or len(request_id)>128:
        raise ValueError("Invalid request ID")
    if not isinstance(reserved_usd,Decimal) or not reserved_usd.is_finite() or reserved_usd<=0:
        raise ValueError("Invalid reservation")
    if not isinstance(usage,UsageCost) or usage.billing_verified:
        raise ValueError("Expected an unverified token estimate")
    estimated=usage.estimated_usd
    if not estimated.is_finite() or estimated<0:
        raise ValueError("Invalid estimate")
    # Never release an uncertain hold; this is a preview only.
    return ReconciliationCandidate(request_id,reserved_usd,estimated,
                                   Decimal("0"),"awaiting_provider_verification")
