"""
Log Cleaner — Phase 1
Strips noise from raw GitHub Actions log lines and extracts
the cleanest possible error window for the classifier.
"""

import re

# Patterns to strip from log lines
_STRIP_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+"),  # timestamps
    re.compile(r"^\[\d+\]\s+"),                                        # step numbers
    re.compile(r"^##\[.*?\]"),                                         # GitHub group markers
    re.compile(r"\x1b\[[0-9;]*m"),                                     # ANSI colour codes
]

# Lines that are pure noise — drop entirely
_NOISE_PATTERNS = [
    re.compile(r"^\s*$"),                          # blank lines
    re.compile(r"^Post job cleanup"),
    re.compile(r"^Cleaning up orphan processes"),
    re.compile(r"^Set up job"),
    re.compile(r"^Complete job"),
    re.compile(r"^Run actions/"),
    re.compile(r"^::set-output"),
    re.compile(r"^##\[endgroup\]"),
    re.compile(r"^##\[group\]"),
]

# Lines that signal the error zone — prioritise these
_ERROR_SIGNALS = [
    "error",
    "exception",
    "traceback",
    "failed",
    "fatal",
    "modulenotfounderror",
    "importerror",
    "typeerror",
    "assertionerror",
    "validationerror",
    "operationalerror",
]


def clean(raw_lines: list[str]) -> list[str]:
    """
    Strip noise from raw log lines.

    Args:
        raw_lines: Lines straight from the GitHub log ZIP

    Returns:
        Cleaned lines, ready for the classifier
    """
    cleaned = []
    for line in raw_lines:
        # Strip known prefixes
        for pattern in _STRIP_PATTERNS:
            line = pattern.sub("", line)
        line = line.rstrip()

        # Drop noise lines
        if any(p.search(line) for p in _NOISE_PATTERNS):
            continue

        cleaned.append(line)

    return cleaned


def extract_error_window(cleaned_lines: list[str], window: int = 50) -> list[str]:
    """
    Find the densest cluster of error signals and return
    a focused window around it.

    Falls back to the last `window` lines if no signals found.

    Args:
        cleaned_lines: Output from clean()
        window:        Number of lines to return

    Returns:
        The most relevant slice of the log for classification
    """
    if not cleaned_lines:
        return []

    # Find the last line containing an error signal
    last_error_idx = -1
    for i, line in enumerate(cleaned_lines):
        if any(sig in line.lower() for sig in _ERROR_SIGNALS):
            last_error_idx = i

    if last_error_idx == -1:
        # No clear error signal — use tail of log
        return cleaned_lines[-window:]

    # Return window centred around the last error line
    start = max(0, last_error_idx - (window // 2))
    end   = min(len(cleaned_lines), start + window)
    return cleaned_lines[start:end]


def clean_and_extract(raw_lines: list[str], window: int = 50) -> list[str]:
    """
    Convenience: clean raw lines then extract error window.

    Args:
        raw_lines: Raw lines from fetcher.py
        window:    Target window size (default from ERROR_WINDOW_LINES)

    Returns:
        Clean, focused error window ready for the classifier
    """
    cleaned = clean(raw_lines)
    return extract_error_window(cleaned, window=window)
