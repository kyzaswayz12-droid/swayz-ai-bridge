"""One-shot API connectivity test, disabled by default; never prints secrets."""
import argparse
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from .budget import BudgetStore, BudgetLimits
from .emergency_stop import EmergencyStop
from .secret_file import load_provider_keys
from .providers import (prepare_openai_request, prepare_anthropic_request,
                        openai_response, anthropic_response)
from .http_transport import provider_transport
from .response_diagnostics import openai_metadata

def smoke(provider: str, *, secrets: Path, budget_db: Path,
          control_db: Path | None = None, model: str, execute=False,
          transport=provider_transport):
    if provider not in ("openai","anthropic"):
        raise ValueError("Invalid provider")
    if not execute:
        return {"provider":provider,"state":"disabled"}
    if control_db is None or not control_db.is_file():
        raise PermissionError("Existing emergency stop required")
    control=EmergencyStop(str(control_db))
    try:
        if not control.is_stopped():
            raise PermissionError("Agent must remain stopped during smoke test")
    finally:
        control.close()
    if not isinstance(model,str) or not model or len(model)>128 or any(c.isspace() for c in model):
        raise ValueError("Invalid model")
    keys=load_provider_keys(secrets)
    key=keys["OPENAI_API_KEY" if provider=="openai" else "ANTHROPIC_API_KEY"]
    instruction="Reply only OK."
    task="Connectivity test: reply OK."
    payload=(prepare_openai_request(model,instruction,task,max_output_tokens=32)
             if provider=="openai" else
             prepare_anthropic_request(model,instruction,task,max_tokens=32))
    if not budget_db.parent.is_dir() or budget_db.is_symlink():
        raise ValueError("Invalid budget database")
    ledger=BudgetStore(str(budget_db))
    request_id="smoke-"+uuid.uuid4().hex
    try:
        ledger.reserve(request_id,Decimal("0.10"),BudgetLimits(Decimal("5.00"),20,Decimal("0.50")),
                       datetime.now(timezone.utc))
        raw=transport(provider,payload,key)
        if provider=="openai":
            meta=openai_metadata(raw)
            if not meta["output_text_present"]:
                return {"provider":provider,"state":"no_output_text",
                        "status":meta["status"],"incomplete_reason":meta["incomplete_reason"],
                        "input_tokens":meta["input_tokens"],"output_tokens":meta["output_tokens"],
                        "reasoning_tokens":meta["reasoning_tokens"],
                        "reserved_usd":"0.10","request_id":request_id}
        response=openai_response(raw) if provider=="openai" else anthropic_response(raw)
        return {"provider":provider,"state":"responded",
                "input_tokens":response.input_tokens,"output_tokens":response.output_tokens,
                "reserved_usd":"0.10","request_id":request_id}
    finally:
        ledger.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--provider",choices=("openai","anthropic"),required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--secrets",type=Path,required=True)
    parser.add_argument("--budget-db",type=Path,required=True)
    parser.add_argument("--control-db",type=Path,required=True)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    print(json.dumps(smoke(args.provider,secrets=args.secrets,budget_db=args.budget_db,
                           control_db=args.control_db,model=args.model,execute=args.execute)))
if __name__=="__main__":
    main()
