"""Fail-closed owner-approved USD-to-GBP rate loader.

This validates a local owner-reviewed record, not a live FX quote.
A separate trusted service must protect the file and verify the source.
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path


def load_approved_gbp_per_usd(path, *, today=None):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > 4096:
        raise ValueError("Missing or unsafe FX approval")
    data = json.loads(p.read_text(encoding="utf-8"))
    required = {"base", "quote", "gbp_per_usd", "verified_by_owner",
                "verified_on", "expires_on", "source_url"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Invalid FX approval schema")
    if data["base"] != "USD" or data["quote"] != "GBP":
        raise ValueError("Invalid FX pair")
    if data["verified_by_owner"] is not True:
        raise PermissionError("FX rate not owner approved")
    now = today or date.today()
    checked = date.fromisoformat(data["verified_on"])
    expires = date.fromisoformat(data["expires_on"])
    if checked > now or expires < now or expires < checked:
        raise PermissionError("FX approval expired")
    if not isinstance(data["source_url"], str) or not data["source_url"].startswith("https://"):
        raise ValueError("FX source required")
    if isinstance(data["gbp_per_usd"], bool) or not isinstance(data["gbp_per_usd"], str):
        raise ValueError("FX rate must be decimal string")
    rate = Decimal(data["gbp_per_usd"])
    if not rate.is_finite() or rate <= 0:
        raise ValueError("Invalid FX rate")
    return rate
