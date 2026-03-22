"""
phase2/tools/github_file.py — Fetch file content from GitHub API.

Used by context_builder when affected_file is a GitHub Actions runner path
(/home/runner/work/...) that doesn't exist locally.

fetch_file(repo, path, ref) → str | None
  GET /repos/{repo}/contents/{path}?ref={ref}
  Returns decoded file content or None on any failure.
  Never raises.
"""

import base64
import os
import re
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

# GitHub Actions workspace path pattern
# Format: /home/runner/work/{repo-dir}/{repo-dir}/{relative-path}
_RUNNER_PATH_RE = re.compile(r"^/home/runner/work/[^/]+/[^/]+/(.+)$")


def extract_relative_path(absolute_path: str) -> str | None:
    """
    Extract repo-relative path from a GitHub Actions runner absolute path.

    Example:
        /home/runner/work/-agent-x-test-repo/-agent-x-test-repo/src/main.py
        → src/main.py

    Returns None if the path doesn't match the runner pattern.
    """
    m = _RUNNER_PATH_RE.match(absolute_path)
    if m:
        return m.group(1)
    return None


def fetch_file(
    repo: str,
    path: str,
    ref: str = "main",
) -> str | None:
    """
    Fetch file content from GitHub API.

    Args:
        repo: Repository in "owner/repo" format.
        path: Repo-relative file path (e.g. "src/main.py").
        ref:  Branch, tag, or commit SHA. Defaults to "main".

    Returns:
        Decoded file content as string, or None on 404 / any failure.
        Never raises.
    """
    import requests

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        log.warning("github_file.no_token", repo=repo, path=path)
        return None

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    params: dict[str, str] = {"ref": ref}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10.0)

        if response.status_code == 404:
            log.warning("github_file.not_found", repo=repo, path=path, ref=ref)
            return None

        response.raise_for_status()
        data = response.json()

        # GitHub API returns base64-encoded content with newlines
        raw = data.get("content", "")
        content = base64.b64decode(raw).decode("utf-8")

        log.info(
            "github_file.fetched",
            repo=repo,
            path=path,
            ref=ref,
            bytes=len(content),
        )
        return content

    except Exception as exc:
        log.warning("github_file.fetch_error", repo=repo, path=path, error=str(exc))
        return None


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    # Test path extraction
    runner_path = "/home/runner/work/-agent-x-test-repo/-agent-x-test-repo/main.py"
    rel = extract_relative_path(runner_path)
    assert rel == "main.py", f"expected 'main.py', got {rel!r}"
    print(f"PASS  extract_relative_path: {runner_path!r} → {rel!r}")

    # Test fetch (requires GITHUB_TOKEN)
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        content = fetch_file("DevSiddh/-agent-x-test-repo", "main.py")
        if content:
            print(f"PASS  fetch_file: {len(content)} bytes fetched")
        else:
            print("PASS  fetch_file: returned None (file may not exist)")
    else:
        print("SKIP  fetch_file: GITHUB_TOKEN not set")

    print("github_file.py smoke test PASSED")
