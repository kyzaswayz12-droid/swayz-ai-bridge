"""Restricted GitHub REST adapter for draft-only Swayz delivery.

A GitHub App installation token scoped to this repository must be supplied by
the operator. This adapter exposes no merge, deployment, delete, or workflow
modification methods. Never log or store the token.
"""
import base64
import json
import re
import urllib.error
import urllib.request

REPO = "kyzaswayz12-droid/swayz-ai-bridge"
SHA = re.compile(r"^[a-f0-9]{40}$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PermissionError("GitHub redirects forbidden")


class DraftOnlyGitHub:
    swayz_draft_only = True

    def __init__(self, token, *, opener=None):
        if not isinstance(token, str) or not token.strip() or "\n" in token or "\r" in token:
            raise PermissionError("Scoped GitHub installation token required")
        self._token = token
        self._opener = opener or urllib.request.build_opener(NoRedirect)

    def _call(self, method, suffix, data=None):
        if not suffix.startswith("/") or "?" in suffix or ".." in suffix:
            raise ValueError("Invalid GitHub route")
        url = "https://api.github.com/repos/" + REPO + suffix
        body = json.dumps(data, separators=(",", ":")).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method, headers={
            "Authorization": "Bearer " + self._token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json"})
        try:
            with self._opener.open(req, timeout=15) as response:
                raw = response.read(131073)
        except urllib.error.HTTPError as exc:
            raise RuntimeError("GitHub operation rejected (HTTP " + str(exc.code) + ")") from None
        if len(raw) > 131072:
            raise RuntimeError("GitHub response too large")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise RuntimeError("Invalid GitHub response")
        return result

    @staticmethod
    def _repo(repo):
        if repo != REPO:
            raise PermissionError("Repository not approved")

    def read_branch_head(self, repo, branch):
        self._repo(repo)
        if branch not in ("main", "feature/swayz-autonomous-dev-agent"):
            raise PermissionError("Base branch not approved")
        result = self._call("GET", "/git/ref/heads/" + branch)
        sha = result.get("object", {}).get("sha")
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise RuntimeError("Invalid branch SHA")
        return sha

    def branch_exists(self, repo, branch):
        self._repo(repo)
        self._branch(branch)
        try:
            self._call("GET", "/git/ref/heads/" + branch)
            return True
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return False
            raise

    @staticmethod
    def _branch(branch):
        if not isinstance(branch, str) or not re.fullmatch(r"agent/[a-z0-9][a-z0-9-]{0,48}", branch):
            raise PermissionError("Unsafe development branch")

    def create_branch(self, repo, branch, sha):
        self._repo(repo)
        self._branch(branch)
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise PermissionError("Invalid base SHA")
        self._call("POST", "/git/refs", {"ref": "refs/heads/" + branch, "sha": sha})

    def put_new_file(self, repo, branch, path, content):
        self._repo(repo)
        self._branch(branch)
        from .change_set import validate_change_set
        validated = validate_change_set({path: content})
        if path.startswith((".github/", "deploy/", "config/")):
            raise PermissionError("Protected path")
        encoded = base64.b64encode(validated[path].encode()).decode()
        from urllib.parse import quote
        self._call("PUT", "/contents/" + quote(path, safe="/"), {
            "message": "Swayz reviewed development change: " + path,
            "content": encoded, "branch": branch})

    def create_pull_request(self, repo, *, base_branch, head_branch, title, body, draft):
        self._repo(repo)
        self._branch(head_branch)
        if base_branch not in ("main", "feature/swayz-autonomous-dev-agent"):
            raise PermissionError("Invalid base branch")
        if draft is not True:
            raise PermissionError("Only draft pull requests allowed")
        if not isinstance(title, str) or len(title) > 160 or not isinstance(body, str) or len(body) > 4000:
            raise ValueError("Invalid PR metadata")
        result = self._call("POST", "/pulls", {
            "base": base_branch, "head": head_branch, "title": title,
            "body": body, "draft": True})
        if result.get("draft") is not True:
            raise PermissionError("GitHub did not confirm draft PR")
        return result
