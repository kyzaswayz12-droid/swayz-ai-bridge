"""A single, explicitly invoked two-provider collaboration.

Requires a separate stopped-agent control, secure credentials and persistent
budget reservations for both calls. No retries, Git writes or trading actions.
This is not a background worker or a complete cost reconciliation system.
"""
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .budget import BudgetStore, BudgetLimits
from .collaboration import collaborate
from .emergency_stop import EmergencyStop
from .http_transport import provider_transport
from .providers import (prepare_openai_request, prepare_anthropic_request,
                        openai_response, anthropic_response)
from .secret_file import load_provider_keys
from .response_diagnostics import openai_metadata
from .collaboration_cost_preview import preview_task
from .collaboration_preflight import preflight

LIMITS=BudgetLimits(Decimal("5.00"),20,Decimal("0.50"))
RESERVATION=Decimal("0.50")  # legacy maximum per request, not default hold

def run_once(task: str, *, secrets: Path, budget_db: Path, control_db: Path,
             openai_model: str, claude_model: str, execute: bool=False,
             transport=provider_transport,
             openai_rate_card: Path | None = None,
             claude_rate_card: Path | None = None):
    if not execute:
        return {"state":"disabled","provider_calls":0}
    if openai_rate_card is None or claude_rate_card is None:
        raise PermissionError("Approved rate cards required for live execution")
    preflight(task,openai_card=openai_rate_card,claude_card=claude_rate_card,
              openai_model=openai_model,claude_model=claude_model)
    if not isinstance(task,str) or not 1<=len(task.strip())<=1500:
        raise ValueError("Invalid task")
    if not control_db.is_file():
        raise PermissionError("Missing emergency-stop control")
    control=EmergencyStop(str(control_db))
    try:
        if not control.is_stopped():
            raise PermissionError("Agent must remain stopped for one-shot test")
    finally:
        control.close()
    preview=preview_task(task,openai_model=openai_model,claude_model=claude_model)
    holds={"openai":preview.openai_reservation_usd,
           "anthropic":preview.claude_reservation_usd}
    keys=load_provider_keys(secrets)
    ledger=BudgetStore(str(budget_db))
    request_ids=[]
    reserved_total=Decimal("0")
    usage=[]
    # Pricing is intentionally not inferred from token counts here.
    def call(provider,model,instruction,prompt,max_tokens):
        if provider=="openai":
            payload=prepare_openai_request(model,instruction,prompt,max_output_tokens=max_tokens)
            parser=openai_response
            key=keys["OPENAI_API_KEY"]
        else:
            payload=prepare_anthropic_request(model,instruction,prompt,max_tokens=max_tokens)
            parser=anthropic_response
            key=keys["ANTHROPIC_API_KEY"]
        if provider=="anthropic" and len(prompt.encode("utf-8"))>12000:
            raise ValueError("Review payload too large; no Claude request made")
        request_id="collab-"+uuid.uuid4().hex
        reserved=ledger.reserve(request_id,holds[provider],LIMITS,datetime.now(timezone.utc))
        if reserved is not True:
            raise PermissionError("Budget reservation refused")
        nonlocal reserved_total
        reserved_total+=holds[provider]
        request_ids.append(request_id)
        raw=transport(provider,payload,key)
        if provider=="openai":
            metadata=openai_metadata(raw)
            if not metadata["output_text_present"]:
                raise ValueError("OpenAI returned no usable proposal; Claude review not started")
        response=parser(raw)
        usage.append({"provider":provider,"model":model,
                      "input_tokens":response.input_tokens,
                      "output_tokens":response.output_tokens,
                      "billing_verified":False})
        return response.text
    try:
        def coder(instruction):
            return call("openai",openai_model,
                "Produce a concise, non-executable development proposal in plain text.",
                instruction,1024)
        def reviewer(instruction,proposal,digest):
            return call("anthropic",claude_model,
                "Review the proposal. Return ONLY a JSON object with exactly keys "
                "proposal_sha256 (the provided hash), approved (boolean), findings "
                "(array of nonempty strings). Reject unsafe or unsupported claims.",
                json.dumps({"task":instruction,"proposal":proposal,"proposal_sha256":digest}),
                512)
        result=collaborate(task,coder,reviewer)
        return {"state":result.state,"proposal_sha256":result.proposal_sha256,
                "reviewer_approved":result.approved_by_reviewer,
                "findings":list(result.findings),"request_ids":request_ids,
                "token_usage":usage,
                "reserved_usd":str(reserved_total),
                "github_writes":0,"live_trading":False}
    finally:
        ledger.close()
