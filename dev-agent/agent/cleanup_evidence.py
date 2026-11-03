"""Interpret simulated container cleanup evidence without executing commands.

A Docker CLI error is not sufficient proof that a container is absent.
This module is deliberately independent of the production Docker daemon.
"""


def cleanup_evidence_verified(*, container_name, inspect_exit_code,
                              inspect_stderr, daemon_healthy):
    """Return true only for a narrow, independently corroborated absence.

    This is a conservative offline predicate, not a production cleanup
    certificate. The future executor must still inspect the exact container
    identity and verify the daemon is responsive after attempting cleanup.
    """
    if not isinstance(container_name, str) or not container_name.startswith("swayz-test-"):
        return False
    if type(inspect_exit_code) is not int or inspect_exit_code != 1:
        return False
    if daemon_healthy is not True:
        return False
    if not isinstance(inspect_stderr, str):
        return False
    return inspect_stderr.strip() == f"Error: No such object: {container_name}"
