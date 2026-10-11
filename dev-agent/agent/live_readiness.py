"""Read-only live-provider readiness checks. Never makes an API request."""
from dataclasses import dataclass
from pathlib import Path
from .secret_file import load_provider_keys
from .core import Policy
from .emergency_stop import EmergencyStop

@dataclass(frozen=True)
class Readiness:
    credentials_present: bool
    budget_limit_usd: str
    stopped: bool
    live_calls_enabled: bool

def check_readiness(secret_path: str | Path, stop_db: str | Path) -> Readiness:
    keys=load_provider_keys(secret_path)
    policy=Policy("kyzaswayz12-droid/swayz-ai-bridge")
    control=EmergencyStop(str(stop_db))
    try:
        stopped=control.is_stopped()
    finally:
        control.close()
    return Readiness(
        credentials_present=bool(keys["OPENAI_API_KEY"] and keys["ANTHROPIC_API_KEY"]),
        budget_limit_usd=str(policy.max_daily_budget_usd),
        stopped=stopped,
        live_calls_enabled=policy.enable_model_calls,
    )
