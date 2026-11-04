"""Supervised deployment acceptance criteria for the local executor.

This module is a read-only policy checklist. Passing the checklist does not
authorise activation: actual worker isolation, signed provenance, atomic
admission, and owner approval must still be demonstrated.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Acceptance:
    signed_provenance: bool
    immutable_snapshot: bool
    approved_image: bool
    shared_stop_enforced: bool
    quota_enforced: bool
    budget_enforced: bool
    docker_cleanup_verified: bool
    github_draft_only: bool
    owner_approved: bool


def assess_supervised_acceptance(checks: Acceptance) -> bool:
    if not isinstance(checks, Acceptance):
        raise TypeError("Acceptance evidence required")
    return all(type(getattr(checks, name)) is bool and getattr(checks, name)
               for name in checks.__dataclass_fields__)
