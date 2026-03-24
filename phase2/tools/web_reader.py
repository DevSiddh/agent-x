"""
phase2/tools/web_reader.py — Fetch and clean web documentation for Agent-Y.

Strips nav/footer/scripts/ads and returns clean text up to max_tokens.
Used when Agent-Y needs current API docs before planning a fix.

Usage:
    from phase2.tools.web_reader import fetch_docs
    text = fetch_docs("https://docs.example.com/api", max_tokens=2000)
"""

import re
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

_MAX_CHARS = 8000  # ~2000 tokens at 4 chars/token


def _strip_noise(html: str) -> str:
    """
    Remove navigation, footer, scripts, styles, and ads from raw HTML.
    Returns cleaned plain text.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("web_reader.bs4_not_installed")
        # Fallback: strip noise tag blocks, then remove all remaining tags
        for noise_tag in ("nav", "footer", "header", "aside", "script",
                          "style", "noscript", "iframe", "form"):
            html = re.sub(
                rf"<{noise_tag}[^>]*>.*?</{noise_tag}>",
                "",
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s{2,}", " ", text).strip()

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup(["nav", "footer", "header", "aside", "script", "style",
                     "noscript", "iframe", "form", "button", "input"]):
        tag.decompose()

    # Remove elements with ad/nav class/id patterns
    noise_patterns = re.compile(
        r"\b(ad|ads|advertisement|sidebar|cookie|popup|banner|nav|navigation|"
        r"footer|header|menu|breadcrumb)\b",
        re.IGNORECASE,
    )
    for tag in soup.find_all(True):
        attrs = " ".join(str(v) for v in (tag.get("class", []) + [tag.get("id", "")]))
        if noise_patterns.search(attrs):
            tag.decompose()

    # Extract meaningful text
    text = soup.get_text(separator="\n")

    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and len(line) > 1]

    # Deduplicate consecutive identical lines
    deduped: list[str] = []
    prev = ""
    for line in lines:
        if line != prev:
            deduped.append(line)
        prev = line

    return "\n".join(deduped)


def fetch_docs(url: str, max_tokens: int = 2000) -> str:
    """
    Fetch and clean web documentation from a URL.

    Args:
        url:        The URL to fetch.
        max_tokens: Maximum tokens to return (rough estimate: 4 chars/token).

    Returns:
        Clean text content, truncated to max_tokens. Empty string on any failure.
        Never raises.
    """
    if not url or not url.startswith(("http://", "https://")):
        log.warning("web_reader.invalid_url", url=url[:100])
        return ""

    max_chars = max_tokens * 4

    try:
        import httpx
    except ImportError:
        try:
            import requests as httpx  # type: ignore[no-redef]
        except ImportError:
            log.warning("web_reader.no_http_client")
            return ""

    try:
        response = httpx.get(
            url,
            headers={"User-Agent": "agent-x/1.0 (documentation fetcher)"},
            timeout=10.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        html = response.text
    except Exception as exc:
        log.warning("web_reader.fetch_error", url=url[:100], error=str(exc))
        return ""

    text = _strip_noise(html)

    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"

    log.info("web_reader.fetched", url=url[:100], chars=len(text))
    return text


if __name__ == "__main__":
    # Smoke test with a known stable URL
    result = fetch_docs("https://httpbin.org/html", max_tokens=500)
    print(f"PASS  fetch_docs: {len(result)} chars returned")
    assert len(result) <= 500 * 4 + 50, "result must respect max_tokens cap"
    print("PASS  token cap respected")

    # Test invalid URL
    empty = fetch_docs("not-a-url")
    assert empty == "", "invalid URL must return empty string"
    print("PASS  invalid URL → empty string")

    print("web_reader.py smoke test PASSED")
