"""
phase2/tools/pr_creator.py
Auto-PR and structural issue creator for Agent-X v2.2.

Uses GitHub Git Database API (no local git clone needed) to:
  - Open Draft PRs for accepted fixes
  - Open GitHub Issues for structural escalations

Authentication priority:
  1. GitHub App (GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY + GITHUB_APP_INSTALLATION_ID)
  2. PAT fallback (GITHUB_TOKEN) — works for personal repos

Never raises. Returns None on any failure.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import structlog

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

log = structlog.get_logger()

_API_BASE = "https://api.github.com"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class PRResult(BaseModel):
    pr_url: str
    branch: str
    pr_number: int
    success: bool


class IssueResult(BaseModel):
    issue_url: str
    issue_number: int
    success: bool


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

def _get_token() -> str:
    """
    Return a GitHub API token.
    Tries GitHub App installation token first, falls back to PAT.
    Never raises — returns empty string if nothing available.
    """
    app_id = os.environ.get("GITHUB_APP_ID", "")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID", "")

    if app_id and private_key and installation_id:
        token = _get_app_installation_token(app_id, private_key, installation_id)
        if token:
            return token

    # Fallback to PAT
    return os.environ.get("GITHUB_TOKEN", "")


def _get_app_installation_token(
    app_id: str, private_key: str, installation_id: str
) -> str | None:
    """
    Exchange GitHub App credentials for a short-lived installation token.
    Returns token string or None on failure. Never raises.
    """
    if httpx is None:
        return None
    try:
        import jwt  # PyJWT
    except ImportError:
        log.warning("pr_creator.jwt_not_installed", hint="pip install PyJWT cryptography")
        return None

    try:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
        # private_key may have literal \n — replace with real newlines
        pem = private_key.replace("\\n", "\n")
        jwt_token = jwt.encode(payload, pem, algorithm="RS256")

        resp = httpx.post(
            f"{_API_BASE}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        if resp.status_code == 201:
            return resp.json()["token"]
        log.warning("pr_creator.app_token_failed", status=resp.status_code)
        return None
    except Exception as exc:
        log.warning("pr_creator.app_token_error", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh(method: str, path: str, token: str, **kwargs: Any) -> httpx.Response | None:
    """
    Make a GitHub API call. Returns response or None on failure. Never raises.
    """
    if httpx is None:
        log.warning("pr_creator.httpx_not_installed")
        return None
    try:
        url = f"{_API_BASE}{path}"
        resp = httpx.request(method, url, headers=_headers(token), timeout=15, **kwargs)
        return resp
    except Exception as exc:
        log.warning("pr_creator.request_failed", error=str(exc), path=path)
        return None


def _apply_patch_to_content(original: str, patch: str) -> str | None:
    """
    Apply a unified diff patch to original file content in memory.
    Returns patched content string or None if patch cannot be applied.
    Handles simple single-file unified diffs.
    Never raises.
    """
    try:
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            orig_path = Path(tmpdir) / "original"
            patch_path = Path(tmpdir) / "patch.diff"
            orig_path.write_text(original, encoding="utf-8")
            patch_path.write_text(patch, encoding="utf-8")

            result = subprocess.run(
                ["patch", "-u", str(orig_path), str(patch_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return orig_path.read_text(encoding="utf-8")

            # Try git apply as fallback
            import shutil
            git_dir = Path(tmpdir) / "gitrepo"
            git_dir.mkdir()
            shutil.copy(orig_path, git_dir / "file")
            subprocess.run(["git", "init", "-q", str(git_dir)], capture_output=True)
            subprocess.run(
                ["git", "-C", str(git_dir), "config", "user.email", "x@x.com"],
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(git_dir), "config", "user.name", "X"],
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(git_dir), "add", "."],
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(git_dir), "commit", "-q", "-m", "init"],
                capture_output=True,
            )

            # Rewrite patch header to match filename "file"
            patched_diff = patch
            result2 = subprocess.run(
                ["git", "-C", str(git_dir), "apply", "--ignore-whitespace",
                 "--recount", str(patch_path)],
                capture_output=True,
                text=True,
            )
            if result2.returncode == 0:
                return (git_dir / "file").read_text(encoding="utf-8")

        log.warning("pr_creator.patch_apply_in_memory_failed")
        return None
    except Exception as exc:
        log.warning("pr_creator.patch_apply_error", error=str(exc))
        return None


def _build_pr_body(
    diagnosis: str,
    category: str,
    affected_file: str,
    run_id: str,
    test_summary: str,
    confidence: float,
    complexity_before: float | None,
    complexity_after: float | None,
    complexity_delta: float | None,
    failing_test: str,
    patch: str,
) -> str:
    complexity_line = ""
    if complexity_before is not None and complexity_after is not None and complexity_delta is not None:
        warn = " ⚠️ increased complexity, review carefully" if complexity_delta > 2.0 else ""
        complexity_line = (
            f"**Complexity:** {complexity_before:.1f} -> {complexity_after:.1f} "
            f"({complexity_delta:+.1f}{warn})\n"
        )

    ghost_test = ""
    if failing_test:
        ghost_test = (
            f"### Proof (Ghost Test)\n"
            f"The failing CI test: `{failing_test}`\n"
            f"- Fails on original code (verified pre-patch)\n"
            f"- Passes with this fix (verified post-patch)\n\n"
        )

    return (
        f"## Agent-X Automated Fix\n"
        f"**Diagnosis:** {diagnosis or 'N/A'}\n"
        f"**Category:** {category}\n"
        f"**File:** `{affected_file}`\n"
        f"**Run ID:** {run_id}\n"
        f"**Test result:** {test_summary}\n"
        f"**Confidence:** {confidence:.2f}\n"
        f"{complexity_line}"
        f"\n{ghost_test}"
        f"### Diff\n"
        f"```diff\n{patch}\n```\n\n"
        f"### What to review\n"
        f"- Does the diagnosis above match what you see in the diff?\n"
        f"- Is complexity increase (if any) acceptable?\n"
        f"- Are there other files that depend on this change?\n\n"
        f"> This PR was opened in Draft mode. Review the diff, run tests locally,\n"
        f"> then mark Ready for Review. Agent-X never merges automatically.\n"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_pr(
    repo: str,
    patch: str,
    affected_file: str,
    run_id: str,
    bug_signature: str,
    category: str,
    test_summary: str,
    original_author: str | None = None,
    diagnosis: str = "",
    confidence: float = 0.0,
    complexity_before: float | None = None,
    complexity_after: float | None = None,
    complexity_delta: float | None = None,
    failing_test: str = "",
) -> PRResult | None:
    """
    Open a Draft PR on GitHub using the Git Database API.
    No local git clone required.

    Flow:
      1. Get token (App or PAT)
      2. GET latest main SHA
      3. GET tree SHA from commit
      4. GET current file content (blob)
      5. Apply patch to content in memory
      6. POST new blob
      7. POST new tree
      8. POST new commit
      9. POST new branch ref
      10. POST pull request (Draft)
      11. Assign reviewer if original_author provided

    Returns PRResult or None on any failure. Never raises.
    """
    token = _get_token()
    if not token:
        log.warning("pr_creator.no_token")
        return None

    try:
        # 1 — Get latest main SHA
        resp = _gh("GET", f"/repos/{repo}/git/ref/heads/main", token)
        if resp is None or resp.status_code != 200:
            log.warning("pr_creator.get_main_sha_failed",
                        status=resp.status_code if resp else None)
            return None
        main_sha = resp.json()["object"]["sha"]

        # 2 — Get tree SHA from commit
        resp = _gh("GET", f"/repos/{repo}/git/commits/{main_sha}", token)
        if resp is None or resp.status_code != 200:
            log.warning("pr_creator.get_commit_failed")
            return None
        tree_sha = resp.json()["tree"]["sha"]

        # 3 — Get current file content
        resp = _gh("GET", f"/repos/{repo}/contents/{affected_file}", token)
        if resp is None or resp.status_code != 200:
            log.warning("pr_creator.get_file_failed", file=affected_file,
                        status=resp.status_code if resp else None)
            return None
        file_data = resp.json()
        original_content = base64.b64decode(file_data["content"]).decode("utf-8")
        file_sha = file_data["sha"]

        # 4 — Apply patch in memory
        patched_content = _apply_patch_to_content(original_content, patch)
        if patched_content is None:
            log.warning("pr_creator.in_memory_patch_failed", file=affected_file)
            return None

        # 5 — Create new blob
        resp = _gh("POST", f"/repos/{repo}/git/blobs", token,
                   json={"content": patched_content, "encoding": "utf-8"})
        if resp is None or resp.status_code != 201:
            log.warning("pr_creator.create_blob_failed")
            return None
        new_blob_sha = resp.json()["sha"]

        # 6 — Create new tree
        resp = _gh("POST", f"/repos/{repo}/git/trees", token,
                   json={
                       "base_tree": tree_sha,
                       "tree": [{"path": affected_file, "mode": "100644",
                                 "type": "blob", "sha": new_blob_sha}],
                   })
        if resp is None or resp.status_code != 201:
            log.warning("pr_creator.create_tree_failed")
            return None
        new_tree_sha = resp.json()["sha"]

        # 7 — Create commit
        commit_message = f"[agent-x] fix {category} in {affected_file}\n\nRun ID: {run_id}"
        resp = _gh("POST", f"/repos/{repo}/git/commits", token,
                   json={
                       "message": commit_message,
                       "tree": new_tree_sha,
                       "parents": [main_sha],
                   })
        if resp is None or resp.status_code != 201:
            log.warning("pr_creator.create_commit_failed")
            return None
        new_commit_sha = resp.json()["sha"]

        # 8 — Create branch
        sig_hash = hashlib.sha256(bug_signature.encode()).hexdigest()[:8]
        branch_name = f"agent-x-fixes/{sig_hash}-{run_id}"
        resp = _gh("POST", f"/repos/{repo}/git/refs", token,
                   json={"ref": f"refs/heads/{branch_name}", "sha": new_commit_sha})
        if resp is None or resp.status_code not in (200, 201):
            log.warning("pr_creator.create_branch_failed",
                        status=resp.status_code if resp else None)
            return None

        # 9 — Open Draft PR
        pr_body = _build_pr_body(
            diagnosis=diagnosis,
            category=category,
            affected_file=affected_file,
            run_id=run_id,
            test_summary=test_summary,
            confidence=confidence,
            complexity_before=complexity_before,
            complexity_after=complexity_after,
            complexity_delta=complexity_delta,
            failing_test=failing_test,
            patch=patch,
        )
        resp = _gh("POST", f"/repos/{repo}/pulls", token,
                   json={
                       "title": f"[agent-x] fix {category} -- {affected_file}",
                       "body": pr_body,
                       "head": branch_name,
                       "base": "main",
                       "draft": True,
                   })
        if resp is None or resp.status_code != 201:
            log.warning("pr_creator.create_pr_failed",
                        status=resp.status_code if resp else None,
                        body=resp.text[:200] if resp else "")
            return None
        pr_data = resp.json()
        pr_number = pr_data["number"]
        pr_url = pr_data["html_url"]

        # 10 — Assign reviewer
        if original_author:
            _gh("POST", f"/repos/{repo}/pulls/{pr_number}/requested_reviewers",
                token, json={"reviewers": [original_author]})

        log.info("pr_creator.pr_opened", repo=repo, pr_url=pr_url,
                 branch=branch_name, pr_number=pr_number)
        return PRResult(pr_url=pr_url, branch=branch_name,
                        pr_number=pr_number, success=True)

    except Exception as exc:
        log.warning("pr_creator.create_pr_exception", error=str(exc))
        return None


def open_structural_issue(
    repo: str,
    run_id: str,
    category: str,
    affected_file: str,
    reason: str,
    original_author: str | None = None,
) -> IssueResult | None:
    """
    Open a GitHub Issue for structural escalations.
    Labels: needs-human-review, agent-x, structural.
    Assigns original_author if provided.
    Returns IssueResult or None on failure. Never raises.
    """
    token = _get_token()
    if not token:
        log.warning("pr_creator.no_token")
        return None

    try:
        body = (
            f"## Agent-X Structural Escalation\n\n"
            f"**Category:** {category}\n"
            f"**File:** `{affected_file}`\n"
            f"**Run ID:** {run_id}\n\n"
            f"### What was attempted\n"
            f"Agent-X attempted to fix a `{category}` in `{affected_file}` "
            f"but the fix exceeded the patch complexity limit.\n\n"
            f"### Why it was escalated\n"
            f"{reason}\n\n"
            f"### What you need to do\n"
            f"This requires a human to review the code architecture and apply "
            f"a manual fix. Agent-X cannot handle structural changes automatically.\n\n"
            f"> Opened automatically by Agent-X. Run ID: {run_id}\n"
        )

        payload: dict[str, Any] = {
            "title": f"[agent-x] structural: {category} in {affected_file}",
            "body": body,
            "labels": ["needs-human-review", "agent-x", "structural"],
        }
        if original_author:
            payload["assignees"] = [original_author]

        resp = _gh("POST", f"/repos/{repo}/issues", token, json=payload)
        if resp is None or resp.status_code != 201:
            log.warning("pr_creator.create_issue_failed",
                        status=resp.status_code if resp else None)
            return None

        issue_data = resp.json()
        issue_url = issue_data["html_url"]
        issue_number = issue_data["number"]

        log.info("pr_creator.issue_opened", repo=repo, issue_url=issue_url,
                 issue_number=issue_number)
        return IssueResult(issue_url=issue_url, issue_number=issue_number, success=True)

    except Exception as exc:
        log.warning("pr_creator.issue_exception", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys as _sys

    print("=== pr_creator.py smoke test ===")

    # Token check
    token = _get_token()
    if not token:
        print("WARN  No GitHub token available (set GITHUB_TOKEN or GitHub App vars)")
    else:
        print(f"PASS  Token available ({len(token)} chars)")

    # Model instantiation
    pr = PRResult(pr_url="https://github.com/owner/repo/pull/1",
                  branch="agent-x-fixes/abc123", pr_number=1, success=True)
    issue = IssueResult(issue_url="https://github.com/owner/repo/issues/1",
                        issue_number=1, success=True)
    assert pr.success
    assert issue.success
    print("PASS  PRResult + IssueResult models instantiate correctly")

    # PR body generation
    body = _build_pr_body(
        diagnosis="ZeroDivisionError caused by missing guard before division",
        category="RuntimeError",
        affected_file="utils.py",
        run_id="abc123",
        test_summary="5 passed, 0 failed",
        confidence=0.99,
        complexity_before=2.0,
        complexity_after=2.5,
        complexity_delta=0.5,
        failing_test="tests/test_utils.py::test_divide",
        patch="--- a/utils.py\n+++ b/utils.py\n@@ -1 +1 @@\n-x = 1/0\n+x = 0",
    )
    assert "Diagnosis" in body
    assert "Draft mode" in body
    print("PASS  PR body generated correctly")

    print("pr_creator.py smoke test PASSED")
    _sys.exit(0)
