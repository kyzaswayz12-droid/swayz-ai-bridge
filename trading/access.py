"""Fail-closed entitlement checks for targeted subscriber publications.

Channel-wide Telegram or Discord messages cannot enforce per-member tiers;
premium distribution requires private destinations and verified membership.
"""
from .entitlements import SubscriberRegistry

def authorised_recipients(registry: SubscriberRegistry, subscriber_ids: list[str],
                          required_tier: str, now: int) -> list[str]:
    if required_tier not in ("free", "premium"):
        raise ValueError("Invalid required tier")
    # Deduplicate while preserving order; fail closed for missing or expired entries.
    return [subscriber for subscriber in dict.fromkeys(subscriber_ids)
            if registry.eligible(subscriber, required_tier, now=now)]
