"""Explicitly gated model call runner.

Activation is process-local and must be granted by the owner-controlled service.
The transport and parser are injected for offline tests.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from .budget import BudgetStore, BudgetLimits
from .dispatcher import DispatchPolicy, dispatch_review_request
from .http_transport import provider_transport

@dataclass(frozen=True)
class Activation:
    owner_approved: bool = False
    provider_calls_enabled: bool = False
    git_writes_enabled: bool = False
    live_trading_enabled: bool = False

def run_provider_call(*, activation: Activation, provider: str, request_id: str,
                      model: str, instruction: str, task: str, api_key: str,
                      budget: BudgetStore, limits: BudgetLimits,
                      estimate_usd: Decimal, now: datetime,
                      transport=provider_transport, emergency_stop=None):
    if emergency_stop is None:
        raise PermissionError("Persistent emergency-stop control required")
    emergency_stop.require_running()
    if not activation.owner_approved or not activation.provider_calls_enabled:
        raise PermissionError("Owner approval and model-call activation required")
    if activation.git_writes_enabled or activation.live_trading_enabled:
        raise PermissionError("Model calls cannot enable Git writes or live trading")
    return dispatch_review_request(
        provider=provider, request_id=request_id, model=model,
        instruction=instruction, task=task, api_key=api_key,
        transport=transport, budget=budget, limits=limits,
        estimated_cost_usd=estimate_usd, now=now,
        policy=DispatchPolicy(enabled=True))
