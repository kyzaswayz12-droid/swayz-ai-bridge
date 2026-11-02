"""Offline autonomous-dispatch simulation; never performs paid provider calls.

Production dispatch must be implemented separately after security review.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from .job_request_reservation import reserve_job_api_request
from .emergency_stop import EmergencyStop
from .providers import (
    ModelResponse, prepare_openai_request, prepare_anthropic_request,
    openai_response, anthropic_response,
)


@dataclass(frozen=True)
class AutonomousDispatchResult:
    response: ModelResponse
    provider_calls: int = 0


def simulate_review_request(*, job_db: str, budget_db: str, job_id: str,
                            request_id: str, provider: str, model: str,
                            instruction: str, task: str, maximum_usd: Decimal,
                            approved_gbp_per_usd: Decimal, now: datetime,
                            mock_response: bytes, control_db: str) -> AutonomousDispatchResult:
    if not isinstance(control_db, str) or not control_db.strip():
        raise PermissionError("Emergency-stop control required")
    from pathlib import Path
    if not Path(control_db).is_file():
        raise PermissionError("Emergency-stop control missing")
    control = EmergencyStop(control_db)
    try:
        control.require_running()
    finally:
        control.close()
    if provider == "openai":
        prepare_openai_request(model, instruction, task)
        parser = openai_response
    elif provider == "anthropic":
        prepare_anthropic_request(model, instruction, task)
        parser = anthropic_response
    else:
        raise ValueError("Unsupported provider")
    if not isinstance(mock_response, bytes) or len(mock_response) > 1024 * 1024:
        raise ValueError("Invalid mock response")
    if not reserve_job_api_request(
        job_db=job_db, budget_db=budget_db, job_id=job_id,
        request_id=request_id, provider=provider, maximum_usd=maximum_usd,
        approved_gbp_per_usd=approved_gbp_per_usd, now=now
    ):
        raise ValueError("Duplicate API request")
    return AutonomousDispatchResult(parser(mock_response))
