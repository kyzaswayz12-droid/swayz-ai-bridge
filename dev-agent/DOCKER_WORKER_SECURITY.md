# Docker test-worker security boundary

The `test_sandbox.py` and `test_executor.py` modules plan and execute
restricted Docker test commands. **Do not run them in the AI coordinator's
security context.** Docker daemon access can grant host-level privileges.

## Required worker architecture
- A separate trusted test-worker service receives only approved test-job IDs.
- The coordinator must not belong to the `docker` group or mount the Docker socket.
- The worker retrieves an immutable, reviewed code snapshot by exact commit SHA.
- The worker verifies image digest, workspace provenance and command identity.
- Run with no network, read-only code, non-root UID, dropped capabilities,
  process/memory/CPU limits, no-new-privileges and no host secrets.
- Add a hardened seccomp/AppArmor profile and restrict mounts to a disposable
  worker-owned directory. No production directories may be mounted.
- Kill the entire container on timeout; reconcile orphaned containers on restart.
- Reject symlinks, bind-mount escape paths and unexpected nested mounts.
- Verify actual Docker behaviour on Droplet 2 before enabling worker execution.

## Current limitations
- The executor has only been tested with injected subprocess mocks.
- The Python image digest is intentionally not configured; the placeholder
  constant must never be used for a real run.
- `subprocess.run` timeouts alone do not prove container termination.
- This is not yet a secure multi-tenant sandbox.
- GitHub PR publication and autonomous operation remain disabled.
