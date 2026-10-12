"""Read-only Git checkout attestation via an injected, trusted Git runner.

No subprocess is launched by this module. The trusted worker must own the
runner and an immutable checkout; this is not a remote-origin attestation.
"""
import re
from pathlib import Path

_SHA = re.compile(r"^[a-f0-9]{40}$")


def attest_git_checkout(workspace, expected_sha, *, runner):
    root = Path(workspace)
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise PermissionError("Invalid checkout")
    if root.resolve() != root:
        raise PermissionError("Noncanonical checkout")
    if not isinstance(expected_sha, str) or not _SHA.fullmatch(expected_sha):
        raise ValueError("Invalid expected commit")
    if not callable(runner):
        raise ValueError("Trusted runner required")
    def git(*args):
        result = runner(["git", "-C", str(root), *args])
        if result.returncode != 0:
            raise PermissionError("Git checkout verification failed")
        return result.stdout.strip()
    observed = git("rev-parse", "--verify", "HEAD")
    if observed != expected_sha:
        raise PermissionError("Commit SHA mismatch")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise PermissionError("Checkout has uncommitted or untracked files")
    return observed
