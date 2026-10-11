"""Offline cost preview for a fixed two-model proposal/review cycle.

UTF-8 byte length is only a conservative planning proxy for token count,
not an API-enforced input-token cap or provider billing guarantee.
"""
from dataclasses import dataclass
from decimal import Decimal
from .reference_rates import reference_rate
from .cost_estimates import reservation_for_request

MAX_TASK_BYTES=4096
MAX_REVIEW_BYTES=12000

@dataclass(frozen=True)
class CostPreview:
    openai_reservation_usd: Decimal
    claude_reservation_usd: Decimal
    total_reservation_usd: Decimal
    is_provider_hard_cap: bool = False

def preview_task(task: str, *, openai_model: str="gpt-5-mini",
                 claude_model: str="claude-haiku-4-5-20251001") -> CostPreview:
    if not isinstance(task,str) or not task.strip():
        raise ValueError("Task required")
    size=len(task.encode("utf-8"))
    if size>MAX_TASK_BYTES:
        raise ValueError("Task too large for staging")
    # Allow for instructions, task and provider message overhead in planning.
    openai_input_budget=size+2048
    # Claude sees the task plus the generated proposal; reserve a generous
    # input planning allowance, independent of any output token cap.
    claude_input_budget=MAX_REVIEW_BYTES
    a=reservation_for_request(reference_rate("openai",openai_model),
                              openai_input_budget,1024)
    b=reservation_for_request(reference_rate("anthropic",claude_model),
                              claude_input_budget,512)
    return CostPreview(a,b,a+b)
