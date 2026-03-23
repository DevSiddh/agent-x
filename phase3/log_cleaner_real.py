"""
phase3/log_cleaner_real.py — Real GitHub Actions log cleaner.

Strips ANSI codes, timestamps, and runner metadata from raw CI logs,
then extracts the relevant failure window for the classifier.

Run smoke test:
    python phase3/log_cleaner_real.py
"""

import re
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_LOG_BYTES: int = 200 * 1024  # 200 KB hard cap

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+")
RUNNER_META = re.compile(r"^##\[(?:group|endgroup|warning|error|debug)\]")


# ── Public functions ───────────────────────────────────────────────────────────

def cap_log(raw: str) -> str:
    """
    Cap raw log string to MAX_LOG_BYTES.
    Takes the LAST bytes so the failure (always near end) is preserved.
    """
    log.info("cleaner.cap_log", input_bytes=len(raw.encode("utf-8", errors="ignore")))
    encoded = raw.encode("utf-8", errors="ignore")
    if len(encoded) > MAX_LOG_BYTES:
        encoded = encoded[-MAX_LOG_BYTES:]
        raw = encoded.decode("utf-8", errors="ignore")
    log.info("cleaner.cap_log.done", output_bytes=len(raw.encode("utf-8", errors="ignore")))
    return raw


def clean_real_log(raw: str) -> list[str]:
    """
    Strip ANSI escape codes, ISO timestamps, and GitHub runner metadata lines.
    Returns non-empty stripped lines only.
    """
    log.info("cleaner.clean_real_log", input_lines=len(raw.splitlines()))
    lines: list[str] = []
    for line in raw.splitlines():
        line = ANSI_ESCAPE.sub("", line)
        line = TIMESTAMP.sub("", line)
        if RUNNER_META.match(line):
            continue
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    log.info("cleaner.clean_real_log.done", output_lines=len(lines))
    return lines


def extract_failure_window(lines: list[str], n: int = 40) -> list[str]:
    """
    Find the last line containing an error marker and return n lines around it.
    Biased toward lines BEFORE the marker (tracebacks precede the final error message).
    Falls back to last n lines when no error marker is found.
    """
    log.info("cleaner.extract_failure_window", total_lines=len(lines), window=n)
    markers = (
        # Python
        "ERROR", "Traceback", "FAILED", "Error:", "error:", "Exception",
        # Node.js
        "at Object.<anonymous>", "at Module.", "npm ERR!", "yarn ERR!",
        # PHP
        "PHP Fatal error:", "PHP Warning:", "PHP Parse error:", "PHP Notice:",
        # Java
        "Exception in thread", "Caused by:", "BUILD FAILURE",
    )
    last_idx = -1
    for i, line in enumerate(lines):
        if any(m in line for m in markers):
            last_idx = i

    if last_idx == -1:
        log.info("cleaner.extract_failure_window.fallback", reason="no_error_marker")
        return lines[-n:]

    # Take 75% of window before the marker, 25% after
    # Tracebacks always appear BEFORE the final "Error: Process completed" line
    before = int(n * 0.75)
    after = n - before
    start = max(0, last_idx - before)
    end = min(len(lines), last_idx + after)
    result = lines[start:end]
    log.info("cleaner.extract_failure_window.done", marker_line=last_idx, start=start, end=end)
    return result


# ── Smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    SAMPLE_LOG = (
        "2026-03-21T10:00:00.000Z ##[group]Run python -c ...\n"
        "2026-03-21T10:00:01.000Z \x1b[31mTraceback (most recent call last):\x1b[0m\n"
        "2026-03-21T10:00:01.100Z   File \"<string>\", line 1, in <module>\n"
        "2026-03-21T10:00:01.200Z ModuleNotFoundError: No module named 'setuptools_missing'\n"
        "2026-03-21T10:00:01.300Z ##[endgroup]\n"
        "2026-03-21T10:00:02.000Z Post job cleanup.\n"
    )

    print("--- cap_log ---")
    capped = cap_log(SAMPLE_LOG)
    assert len(capped.encode()) <= MAX_LOG_BYTES
    print(f"capped to {len(capped.encode())} bytes  OK")

    print("\n--- clean_real_log ---")
    cleaned = clean_real_log(SAMPLE_LOG)
    for line in cleaned:
        print(f"  {line!r}")
    assert not any("\x1b" in l for l in cleaned), "ANSI not stripped"
    assert not any("##[" in l for l in cleaned), "runner metadata not stripped"
    assert not any("2026-03-21T" in l for l in cleaned), "timestamps not stripped"
    print(f"{len(cleaned)} lines — ANSI/timestamps/metadata stripped  OK")

    print("\n--- extract_failure_window ---")
    window = extract_failure_window(cleaned, n=4)
    for line in window:
        print(f"  {line!r}")
    assert any("ModuleNotFoundError" in l or "Traceback" in l for l in window)
    print(f"{len(window)} lines — error window extracted  OK")

    print("\nlog_cleaner_real.py smoke test PASSED")
    sys.exit(0)
