"""Approval-gated provider dispatcher with persistent cost reservations.

Transport is injected; no network implementation is enabled in staging.
Failed/uncertain requests retain their reservation to avoid accidental rebilling.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable
from .budget import BudgetLimits, BudgetStore
from .providers import (ModelResponse, openai_response, anthropic_response,
                        prepare_openai_request, prepare_anthropic_request)

@dataclass(frozen=True)
class DispatchPolicy:
    enabled: bool = False
    max_response_bytes: int = 1024 * 1024

def dispatch_review_request(*, provider: str, request_id: str, model: str,
                            instruction: str, task: str, api_key: str,
                            transport: Callable[[str, dict, str], bytes],
                            budget: BudgetStore, limits: BudgetLimits,
                            estimated_cost_usd: Decimal, now: datetime,
                            policy: DispatchPolicy = DispatchPolicy()) -> ModelResponse:
    if not policy.enabled:
        raise PermissionError("Provider dispatch disabled")
    if provider not in ("openai", "anthropic"):
        raise ValueError("Unsupported provider")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("Missing provider credential")
    if not callable(transport):
        raise ValueError("Invalid transport")
    if type(policy.max_response_bytes) is not int or not 1 <= policy.max_response_bytes <= 1024 * 1024:
        raise ValueError("Invalid response limit")
    # Validate the request before reserving any paid-call allowance.
    if provider == "openai":
        payload = prepare_openai_request(model, instruction, task)
        parse = openai_response
    else:
        payload = prepare_anthropic_request(model, instruction, task)
        parse = anthropic_response
    if not budget.reserve(request_id, estimated_cost_usd, limits, now):
        raise ValueError("Duplicate request id")
    # The transport must enforce TLS, host allowlists, deadlines, and no redirects.
    # Reservation remains in place on exceptions or malformed responses.
    response = transport(provider, payload, api_key)
    if not isinstance(response, bytes) or len(response) > policy.max_response_bytes:
        raise ValueError("Invalid or oversized provider response")
    return parse(response)
