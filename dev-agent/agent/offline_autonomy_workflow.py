"""Offline end-to-end admission of one development job and two provider holds.

No provider transport, Docker invocation, GitHub writes or live trading.
A failure retains prior reservations and job admission conservatively.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .daily_job_quota import DailyJobQuota
from .autonomy_gateway import reserve_offline_gateway_request
from .fx_approval import load_approved_gbp_per_usd
from .providers import prepare_openai_request, prepare_anthropic_request


@dataclass(frozen=True)
class OfflineWorkflowResult:
    job_id: str
    request_ids: tuple[str, str]
    reserved_requests: int
    provider_calls: int = 0
    docker_executed: bool = False
    github_writes: int = 0


def stage_offline_collaboration(*, job_db: str, budget_db: str,
                                control_db: str, fx_approval_path: str,
                                job_id: str, openai_request_id: str,
                                anthropic_request_id: str,
                                openai_model: str, anthropic_model: str,
                                task: str, openai_maximum_usd: Decimal,
                                anthropic_maximum_usd: Decimal,
                                now: datetime) -> OfflineWorkflowResult:
    if not isinstance(task, str) or not task.strip():
        raise ValueError("Empty task")
    if openai_request_id == anthropic_request_id:
        raise ValueError("Request IDs must differ")
    # Validate both requests and total maximum cost before consuming a job slot.
    prepare_openai_request(openai_model, "Offline development review", task)
    prepare_anthropic_request(anthropic_model, "Offline development review", task)
    rate = load_approved_gbp_per_usd(fx_approval_path, today=now.date())
    for amount in (openai_maximum_usd, anthropic_maximum_usd):
        if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
            raise ValueError("Invalid maximum request cost")
    if (openai_maximum_usd + anthropic_maximum_usd) * rate > Decimal("5.00"):
        raise ValueError("Combined request maximum exceeds daily GBP cap")
    # Reject a missing/stopped control before consuming a daily job slot.
    if not isinstance(control_db, str) or not Path(control_db).is_file():
        raise PermissionError("Emergency-stop control missing")
    from .emergency_stop import EmergencyStop
    control = EmergencyStop(control_db)
    try:
        control.require_running()
    finally:
        control.close()
    jobs = DailyJobQuota(job_db)
    try:
        if not jobs.admit(job_id, now, daily_limit=20):
            raise ValueError("Duplicate development job")
    finally:
        jobs.close()
    for request_id, provider, model, maximum in (
        (openai_request_id, "openai", openai_model, openai_maximum_usd),
        (anthropic_request_id, "anthropic", anthropic_model, anthropic_maximum_usd),
    ):
        reserve_offline_gateway_request(
            job_db=job_db, budget_db=budget_db, control_db=control_db,
            fx_approval_path=fx_approval_path, job_id=job_id,
            request_id=request_id, provider=provider, model=model,
            instruction="Offline development review", task=task,
            maximum_usd=maximum, now=now)
    return OfflineWorkflowResult(job_id, (openai_request_id, anthropic_request_id), 2)
