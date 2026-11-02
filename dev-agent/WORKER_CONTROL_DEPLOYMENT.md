# Swayz Worker Control — supervised deployment checklist

Status: **NOT DEPLOYED**. This document is not authorisation to start the service.

## Required prerequisites

1. Obtain owner approval for a supervised, non-production control-service test.
2. Verify DigitalOcean firewall permits TCP 8443 only from the Bridge's private address 10.106.0.2/32. Keep SSH administration available.
3. Run as a dedicated unprivileged service identity with **no Docker group**, sudo or shell access.
4. Provision a dedicated TLS certificate with IP SAN 10.106.0.3 and private key. The Bridge must verify certificate identity and trust a pinned CA or certificate. Never disable certificate verification.
5. Provision a distinct random HMAC key (32+ bytes) securely to both peers, outside GitHub, logs and Slack. Ensure file ownership and restrictive permissions.
6. Use persistent replay, emergency-stop and journal databases in a private directory, protected from symlink replacement and shared writers. Back up emergency-stop state.
7. Set SWAYZ_CONTROL_ENABLED=1 only for the supervised test. Bind solely to 10.106.0.3:8443. Do not use 0.0.0.0 or Docker socket mounts.
8. Confirm authenticated status and stop, tampered signature rejection, replay rejection across restarts, stale request rejection, and failure-closed database errors.
9. Confirm stop blocks every actual dispatch path, including jobs already queued. A stop response alone does not prove running work has been terminated.
10. Verify Bridge-to-worker calls use timeouts, TLS verification, no automatic retries for stop, and do not log secrets. Roll back by stopping the control service and retaining stopped state.

## Explicitly not supported yet

- No unattended autonomy or automatic enable/resume endpoint.
- No production deployment, paid model invocation or GitHub write via this service.
- No guarantee of running-container termination; worker executor integration must be audited.
- The existing Droplet 1 Slack container is not updated by these commits.
