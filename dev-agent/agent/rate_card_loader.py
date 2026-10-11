"""Load owner-reviewed rate cards; never silently trust stale or unknown rates.

Rate values are USD per million tokens. The caller must independently check
provider pricing, billing tier, caching and any special token classes.
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from .cost_estimates import RateCard

def load_rate_card(path: str | Path, provider: str, model: str, *,
                   today: date | None=None) -> RateCard:
    if provider not in ("openai","anthropic"):
        raise ValueError("Unknown provider")
    if not isinstance(model,str) or not model:
        raise ValueError("Invalid model")
    p=Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>16384:
        raise ValueError("Missing or unsafe rate card")
    data=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or data.get("provider")!=provider or data.get("model")!=model:
        raise ValueError("Rate card provider/model mismatch")
    if data.get("verified_by_owner") is not True:
        raise PermissionError("Rate card not owner verified")
    checked=date.fromisoformat(data["verified_on"])
    expiry=date.fromisoformat(data["expires_on"])
    now=today or date.today()
    if checked>now or expiry<now or expiry<checked:
        raise PermissionError("Rate card expired or invalid")
    if set(data)!={"provider","model","verified_by_owner","verified_on","expires_on",
                   "input_per_million_usd","output_per_million_usd","source_url"}:
        raise ValueError("Unexpected rate card fields")
    source=data["source_url"]
    if not isinstance(source,str) or not source.startswith("https://"):
        raise ValueError("Verified pricing source required")
    return RateCard(model,Decimal(str(data["input_per_million_usd"])),
                    Decimal(str(data["output_per_million_usd"])))
