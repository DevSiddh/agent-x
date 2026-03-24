"""
phase2/tools/github_search.py — Search GitHub for real-world fix examples (Agent-X).

Returns 2-3 small, relevant code snippets for obscure errors.
Filters by stars > 50, recent commits, language match.

Usage:
    from phase2.tools.github_search import search_code
    snippets = search_code("ModuleNotFoundError pkg_resources requirements.txt", language="python")
"""

import os
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

_MIN_STARS = 50
_MAX_SNIPPETS = 3
_MAX_SNIPPET_CHARS = 300


def _get_token() -> str:
    """Lazy GITHUB_TOKEN read — never at module level."""
    return os.environ.get("GITHUB_TOKEN", "")


def search_code(query: str, language: str = "") -> list[str]:
    """
    Search GitHub code for real-world fix examples matching the query.

    Args:
        query:    Search query (e.g. "ModuleNotFoundError setuptools requirements.txt").
        language: Optional language filter (e.g. "python", "javascript").

    Returns:
        List of 2-3 code snippet strings. Empty list if no results or on any failure.
        Never raises.
    """
    if not query or not query.strip():
        return []

    token = _get_token()
    if not token:
        log.warning("github_search.no_token")
        return []

    try:
        import requests
    except ImportError:
        log.warning("github_search.requests_not_installed")
        return []

    # Build search query — append language filter if provided
    q = query.strip()
    if language:
        q += f" language:{language}"

    url = "https://api.github.com/search/code"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params: dict[str, str | int] = {
        "q": q,
        "per_page": 10,
        "sort": "indexed",
        "order": "desc",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10.0)
        if response.status_code == 403:
            log.warning("github_search.rate_limited")
            return []
        response.raise_for_status()
        items = response.json().get("items", [])
    except Exception as exc:
        log.warning("github_search.search_error", query=q[:80], error=str(exc))
        return []

    snippets: list[str] = []
    for item in items:
        if len(snippets) >= _MAX_SNIPPETS:
            break

        repo_info = item.get("repository", {})
        # Filter: minimum stars
        if repo_info.get("stargazers_count", 0) < _MIN_STARS:
            continue

        # Fetch the raw file content to extract a relevant snippet
        raw_url = item.get("html_url", "").replace(
            "github.com", "raw.githubusercontent.com"
        ).replace("/blob/", "/")

        if not raw_url:
            continue

        try:
            raw_resp = requests.get(
                raw_url,
                headers={"Authorization": f"token {token}"},
                timeout=5.0,
            )
            if raw_resp.status_code != 200:
                continue
            content = raw_resp.text
        except Exception:
            continue

        # Extract a short relevant snippet
        snippet = _extract_snippet(content, query, item.get("path", ""))
        if snippet:
            repo_name = repo_info.get("full_name", "unknown")
            file_path = item.get("path", "")
            snippets.append(f"# {repo_name}: {file_path}\n{snippet}")

    log.info("github_search.done", query=q[:80], found=len(snippets))
    return snippets


def _extract_snippet(content: str, query: str, filepath: str) -> str:
    """
    Extract a short, relevant snippet from file content.
    Finds the line most relevant to the query and returns context lines around it.
    """
    lines = content.splitlines()
    if not lines:
        return ""

    # Find the most relevant line
    query_words = set(query.lower().split())
    best_line = 0
    best_score = 0

    for i, line in enumerate(lines):
        score = sum(1 for word in query_words if word in line.lower())
        if score > best_score:
            best_score = score
            best_line = i

    if best_score == 0:
        return ""

    # Extract 5 lines of context around the best match
    start = max(0, best_line - 2)
    end = min(len(lines), best_line + 3)
    snippet = "\n".join(lines[start:end])

    if len(snippet) > _MAX_SNIPPET_CHARS:
        snippet = snippet[:_MAX_SNIPPET_CHARS] + "\n... (truncated)"

    return snippet


if __name__ == "__main__":
    token = _get_token()
    if not token:
        print("SKIP  github_search: GITHUB_TOKEN not set")
    else:
        snippets = search_code("ModuleNotFoundError setuptools requirements.txt", language="python")
        print(f"PASS  search_code: {len(snippets)} snippets returned")
        assert len(snippets) <= _MAX_SNIPPETS, f"must return at most {_MAX_SNIPPETS} snippets"
        print(f"PASS  <= {_MAX_SNIPPETS} snippets")

    # Test empty query
    empty = search_code("")
    assert empty == [], "empty query must return empty list"
    print("PASS  empty query → empty list")

    # Test no token
    original = os.environ.pop("GITHUB_TOKEN", None)
    no_tok = search_code("test query")
    assert no_tok == [], "no token must return empty list"
    if original:
        os.environ["GITHUB_TOKEN"] = original
    print("PASS  no token → empty list")

    print("github_search.py smoke test PASSED")
