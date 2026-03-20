"""
Log Fetcher — Phase 1
Downloads the GitHub Actions log for a failed workflow run
and returns the last N lines (error window).
"""

import io
import os
import zipfile

import requests
import structlog

log = structlog.get_logger()


def _get_token() -> str:
    """Lazy GITHUB_TOKEN getter — called inside functions, never at module level (P4)."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN is not set")
    return token


def _get_window_size() -> int:
    """Lazy ERROR_WINDOW_LINES getter."""
    return int(os.environ.get("ERROR_WINDOW_LINES", 50))


def fetch_logs(logs_url: str, run_id: int | str) -> list[str]:
    """
    Download and extract the log archive for a failed GitHub Actions run.

    Args:
        logs_url: GitHub API URL for the run's logs (from webhook payload)
        run_id:   Workflow run ID (used for structured logging)

    Returns:
        List of strings — last ERROR_WINDOW_LINES lines of the log

    Raises:
        EnvironmentError: If GITHUB_TOKEN is not set.
    """
    token = _get_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        log.info("fetcher.fetching_logs", run_id=run_id, url=logs_url)
        response = requests.get(logs_url, headers=headers, timeout=30)
        response.raise_for_status()

        raw_lines = _extract_log_lines(response.content)
        window = raw_lines[-_get_window_size():]

        log.info("fetcher.extracted", total_lines=len(raw_lines), window_lines=len(window))
        return window

    except requests.HTTPError as e:
        log.error("fetcher.http_error", error=str(e), run_id=run_id)
        return []
    except requests.Timeout:
        log.error("fetcher.timeout", run_id=run_id)
        return []


def _extract_log_lines(zip_bytes: bytes) -> list[str]:
    """
    Extract all text lines from a GitHub Actions log ZIP archive.
    Files are sorted before iteration to guarantee step order (P9).
    """
    lines: list[str] = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in sorted(zf.namelist()):  # P9 — sorted for deterministic order
                if name.endswith(".txt"):
                    content = zf.read(name).decode("utf-8", errors="replace")
                    lines.extend(content.splitlines())
    except zipfile.BadZipFile:
        log.error("fetcher.bad_zip")

    return lines


if __name__ == "__main__":
    import io
    import zipfile
    from unittest.mock import MagicMock, patch

    os.environ["GITHUB_TOKEN"] = "smoke-token"

    # Build a fake ZIP with 2 log files out of alphabetical order
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2_Build.txt", "build line 1\nbuild line 2\n")
        zf.writestr("1_Setup.txt", "setup line 1\nsetup line 2\n")
    zip_bytes = buf.getvalue()

    lines = _extract_log_lines(zip_bytes)
    assert lines == ["setup line 1", "setup line 2", "build line 1", "build line 2"], \
        f"Sort order wrong: {lines}"
    print("_extract_log_lines sort order: OK")

    mock_response = MagicMock()
    mock_response.content = zip_bytes
    mock_response.raise_for_status = MagicMock()

    with patch("__main__.requests.get", return_value=mock_response):
        result = fetch_logs("https://fake/logs", run_id=42)

    assert len(result) <= 50
    assert "setup line 1" in result
    print(f"fetch_logs smoke test: OK — {len(result)} lines returned")
    print("fetcher.py smoke test PASSED")
