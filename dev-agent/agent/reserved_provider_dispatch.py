"""One-shot, GBP-reserved provider dispatch for a pre-admitted Swayz job.

No background scheduler, credentials on disk, or calls on import.
The privileged caller must enforce shared ledger ownership and explicitly
approve live paid dispatch. No retries; uncertain charges retain their holds.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from .autonomy_gateway import reserve_offline_gateway_request
from .persistent_stop_guard import PersistentStopGuard
from .providers import (
    prepare_openai_request, prepare_anthropic_request,
    openai_response, anthropic_response, ModelResponse,
)
from .http_transport import provider_transport


@dataclass(frozen=True)
class PaidDispatchResult:
    request_id: str
    provider: str
    response: ModelResponse
    reservation_held: bool = True


def dispatch_reserved_provider_once(
    *, job_db: str, budget_db: str, control_db: str,
    fx_approval_path: str, job_id: str, request_id: str,
    provider: str, model: str, instruction: str, task: str,
    maximum_usd: Decimal, now: datetime, api_key: str,
    owner_approved: bool = False, paid_calls_enabled: bool = False,
    transport=provider_transport,
) -> PaidDispatchResult:
    if owner_approved is not True or paid_calls_enabled is not True:
        raise PermissionError("Explicit paid-provider authorisation required")
    if not isinstance(api_key, str) or not api_key.strip():
        raise PermissionError("Provider credential required")
    if transport is not provider_transport and not callable(transport):
        raise ValueError("Invalid provider transport")
    if provider == "openai":
        payload = prepare_openai_request(model, instruction, task)
        parse = openai_response
    elif provider == "anthropic":
        payload = prepare_anthropic_request(model, instruction, task)
        parse = anthropic_response
    else:
        raise PermissionError("Provider not approved")
    guard = PersistentStopGuard(control_db)
    guard.require_running()
    # The existing gateway validates UTC admission, owner-approved FX and
    # atomically reserves against the combined GBP 5/day ledger.
    reserve_offline_gateway_request(
        job_db=job_db, budget_db=budget_db, control_db=control_db,
        fx_approval_path=fx_approval_path, job_id=job_id,
        request_id=request_id, provider=provider, model=model,
        instruction=instruction, task=task, maximum_usd=maximum_usd,
        now=now,
    )
    # Recheck immediately before the only network attempt. A stop after
    # reservation leaves the hold in place rather than allowing a retry.
    guard.require_running()
    body = transport(provider, payload, api_key)
    if not isinstance(body, bytes) or len(body) > 1024 * 1024:
        raise ValueError("Provider response invalid or oversized")
    response = parse(body)
    # Usage alone is not verified billing: retain the full reservation until
    # the existing trusted settlement workflow has reconciled actual costs.
    return PaidDispatchResult(request_id, provider, response)
