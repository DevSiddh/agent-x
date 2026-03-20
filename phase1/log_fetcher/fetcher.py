"""
Log Fetcher — Phase 1
Downloads the GitHub Actions log for a failed workflow run
and returns the last N lines (error window).
"""

import io
import logging
import os
import zipfile

import requests

log = logging.getLogger(__name__)

GITHUB_TOKEN      = os.environ.get("GITHUB_TOKEN", "")
ERROR_WINDOW_LINES = int(os.environ.get("ERROR_WINDOW_LINES", 50))


def fetch_logs(logs_url: str, run_id: int | str) -> list[str]:
    """
    Download and extract the log archive for a failed GitHub Actions run.

    Args:
        logs_url: GitHub API URL for the run's logs (from webhook payload)
        run_id:   Workflow run ID (used for fallback API call)

    Returns:
        List of strings — last ERROR_WINDOW_LINES lines of the log
    """
    if not GITHUB_TOKEN:
        log.error("GITHUB_TOKEN not set — cannot fetch logs")
        return []

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        log.info(f"Fetching logs for run_id={run_id}")
        response = requests.get(logs_url, headers=headers, timeout=30)
        response.raise_for_status()

        # GitHub returns a ZIP archive of log files
        raw_lines = _extract_log_lines(response.content)
        window    = raw_lines[-ERROR_WINDOW_LINES:]

        log.info(f"Extracted {len(raw_lines)} total lines, using last {len(window)}")
        return window

    except requests.HTTPError as e:
        log.error(f"HTTP error fetching logs: {e}")
        return []
    except requests.Timeout:
        log.error("Timeout fetching logs")
        return []
    except Exception as e:
        log.error(f"Unexpected error fetching logs: {e}")
        return []


def _extract_log_lines(zip_bytes: bytes) -> list[str]:
    """
    Extract all text lines from a GitHub Actions log ZIP archive.
    GitHub bundles one .txt file per job step inside the zip.
    """
    lines = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith(".txt"):
                    content = zf.read(name).decode("utf-8", errors="replace")
                    lines.extend(content.splitlines())
    except zipfile.BadZipFile:
        log.error("Response was not a valid ZIP archive")

    return lines
