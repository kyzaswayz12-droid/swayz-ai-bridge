"""Offline admission preflight. Does not enable network or execution.

This is not an atomic cross-ledger transaction: admission is conservative and
may consume a job slot if subsequent reservation fails.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from .daily_job_quota import DailyJobQuota
from .gbp_budget import GBPBudget


@dataclass(frozen=True)
class Admission:
    job_admitted: bool
    request_reserved: bool
    provider_calls: int = 0


def preflight_job_request(*, job_db: str, budget_db: str, job_id: str,
                          request_id: str, provider: str, maximum_usd: Decimal,
                          approved_gbp_per_usd: Decimal, now: datetime,
                          enabled: bool = False) -> Admission:
    if enabled:
        raise PermissionError("Autonomous provider dispatch not yet enabled")
    # No transport is called. Separate ledgers intentionally fail closed.
    jobs = DailyJobQuota(job_db)
    try:
        admitted = jobs.admit(job_id, now, daily_limit=20)
        if not admitted:
            raise ValueError("Duplicate development job")
    finally:
        jobs.close()
    budget = GBPBudget(budget_db)
    try:
        reserved = budget.reserve(request_id, provider, maximum_usd,
                                  approved_gbp_per_usd, now)
        if not reserved:
            raise ValueError("Duplicate API request")
    finally:
        budget.close()
    return Admission(True, True)
