"""Read-only checks for provider credentials; never print their contents."""
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class CredentialStatus:
    openai_configured: bool
    anthropic_configured: bool

def credential_status(environ=None) -> CredentialStatus:
    env=os.environ if environ is None else environ
    return CredentialStatus(
        bool(env.get("OPENAI_API_KEY","").strip()),
        bool(env.get("ANTHROPIC_API_KEY","").strip()),
    )

def require_credentials(environ=None) -> tuple[str,str]:
    env=os.environ if environ is None else environ
    status=credential_status(env)
    if not status.openai_configured or not status.anthropic_configured:
        raise ValueError("Provider credentials are not configured")
    return env["OPENAI_API_KEY"],env["ANTHROPIC_API_KEY"]
