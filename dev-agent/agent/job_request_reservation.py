"""Offline job-scoped API reservations. Does not dispatch or enable execution.

Jobs must be admitted once through DailyJobQuota before requesting budget.
Each request ID is globally unique and may only be reserved once.
"""
from datetime import datetime
from decimal import Decimal
from .daily_job_quota import DailyJobQuota
from .gbp_budget import GBPBudget


def admit_job(*, job_db: str, job_id: str, now: datetime) -> bool:
    store = DailyJobQuota(job_db)
    try:
        return store.admit(job_id, now, daily_limit=20)
    finally:
        store.close()


def reserve_job_api_request(*, job_db: str, budget_db: str, job_id: str,
                            request_id: str, provider: str, maximum_usd: Decimal,
                            approved_gbp_per_usd: Decimal, now: datetime) -> bool:
    # A prior durable job admission is mandatory. This lookup does not
    # consume another daily job slot.
    jobs = DailyJobQuota(job_db)
    try:
        row = jobs.db.execute(
            "SELECT day_utc FROM admitted_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if row is None:
            raise PermissionError("Development job not admitted")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware clock required")
        from datetime import timezone
        if row[0] != now.astimezone(timezone.utc).date().isoformat():
            raise PermissionError("Development job admission not valid today")
    finally:
        jobs.close()
    budget = GBPBudget(budget_db)
    try:
        return budget.reserve(request_id, provider, maximum_usd,
                              approved_gbp_per_usd, now)
    finally:
        budget.close()
