"""Offline-only gateway contract for autonomous provider calls.

There is deliberately no transport, credential or execution argument.
This module validates preconditions and reserves a request, but cannot
make a paid API call. Live integration requires a separately reviewed worker.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .emergency_stop import EmergencyStop
from .fx_approval import load_approved_gbp_per_usd
from .job_request_reservation import reserve_job_api_request
from .providers import prepare_openai_request, prepare_anthropic_request


@dataclass(frozen=True)
class GatewayReservation:
    request_id: str
    provider: str
    reserved: bool
    provider_calls: int = 0


def reserve_offline_gateway_request(*, job_db: str, budget_db: str,
                                    control_db: str, job_id: str,
                                    request_id: str, provider: str,
                                    model: str, instruction: str, task: str,
                                    maximum_usd: Decimal,
                                    fx_approval_path: str,
                                    now: datetime) -> GatewayReservation:
    if not isinstance(control_db, str) or not control_db.strip():
        raise PermissionError("Emergency-stop control required")
    if not Path(control_db).is_file():
        raise PermissionError("Emergency-stop control missing")
    control = EmergencyStop(control_db)
    try:
        control.require_running()
    finally:
        control.close()
    if provider == "openai":
        prepare_openai_request(model, instruction, task)
    elif provider == "anthropic":
        prepare_anthropic_request(model, instruction, task)
    else:
        raise ValueError("Unsupported provider")
    approved_gbp_per_usd = load_approved_gbp_per_usd(
        fx_approval_path, today=now.date())
    accepted = reserve_job_api_request(
        job_db=job_db, budget_db=budget_db, job_id=job_id,
        request_id=request_id, provider=provider, maximum_usd=maximum_usd,
        approved_gbp_per_usd=approved_gbp_per_usd, now=now)
    if not accepted:
        raise ValueError("Duplicate API request")
    return GatewayReservation(request_id, provider, True)
