"""Trusted unattended deployment gate; never activates or releases the stop.

The current worker is callback-based. This gate refuses deployment until the
operator provides real independent signing, executor, repair and GitHub
authorities. A passing CI mock is NOT a deployable service.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class RuntimeAuthorities:
    authenticated_intake: bool = False
    independent_signer: bool = False
    verified_executor: bool = False
    separately_admitted_repair: bool = False
    reviewed_repair_delivery: bool = False
    draft_only_github: bool = False
    gbp_budget_gateway: bool = False
    persistent_stop_guard: bool = False
    protected_service_identity: bool = False

def require_unattended_activation_ready(authorities):
    if not isinstance(authorities, RuntimeAuthorities):
        raise PermissionError("Independent deployment attestation required")
    missing = [name for name, ready in vars(authorities).items() if ready is not True]
    if missing:
        raise PermissionError("Unattended deployment blocked: " + ", ".join(missing))
    return True
