"""
tests/test_log_cleaner_real.py — Tests for phase3/log_cleaner_real.py
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase3.log_cleaner_real import (
    MAX_LOG_BYTES,
    cap_log,
    clean_real_log,
    extract_failure_window,
)


# ── cap_log ────────────────────────────────────────────────────────────────────

class TestCapLog:
    def test_large_input_is_capped(self) -> None:
        raw = "x" * (MAX_LOG_BYTES + 1000)
        result = cap_log(raw)
        assert len(result.encode("utf-8")) <= MAX_LOG_BYTES

    def test_small_input_unchanged(self) -> None:
        raw = "hello world\n" * 10
        result = cap_log(raw)
        assert result == raw

    def test_takes_last_bytes_not_first(self) -> None:
        # Put a sentinel at the END — it must survive capping
        padding = "a" * (MAX_LOG_BYTES + 500)
        sentinel = "FAILURE_HERE"
        raw = padding + sentinel
        result = cap_log(raw)
        assert sentinel in result

    def test_start_of_large_log_is_dropped(self) -> None:
        # Put a sentinel at the START — it must be dropped
        sentinel = "START_MARKER"
        padding = "b" * (MAX_LOG_BYTES + 500)
        raw = sentinel + padding
        result = cap_log(raw)
        assert sentinel not in result

    def test_exactly_at_limit_unchanged(self) -> None:
        raw = "z" * MAX_LOG_BYTES
        # encode is exactly at limit
        result = cap_log(raw)
        assert len(result.encode("utf-8")) == MAX_LOG_BYTES


# ── clean_real_log ─────────────────────────────────────────────────────────────

class TestCleanRealLog:
    def test_ansi_codes_removed(self) -> None:
        raw = "\x1b[31mERROR: something failed\x1b[0m"
        lines = clean_real_log(raw)
        assert len(lines) == 1
        assert "\x1b" not in lines[0]
        assert "ERROR: something failed" in lines[0]

    def test_iso_timestamps_removed(self) -> None:
        raw = "2026-03-21T10:00:01.123Z some log line"
        lines = clean_real_log(raw)
        assert len(lines) == 1
        assert "2026-03-21T" not in lines[0]
        assert "some log line" in lines[0]

    def test_runner_metadata_group_removed(self) -> None:
        raw = "##[group]Run setup step\nactual content\n##[endgroup]"
        lines = clean_real_log(raw)
        assert not any("##[" in l for l in lines)
        assert any("actual content" in l for l in lines)

    def test_runner_metadata_all_types_removed(self) -> None:
        meta_lines = [
            "##[group]something",
            "##[endgroup]",
            "##[warning]some warning",
            "##[error]some error",
            "##[debug]some debug",
        ]
        raw = "\n".join(meta_lines)
        lines = clean_real_log(raw)
        assert lines == []

    def test_empty_lines_not_in_output(self) -> None:
        raw = "line one\n\n   \nline two\n\n"
        lines = clean_real_log(raw)
        assert lines == ["line one", "line two"]

    def test_real_log_sample(self) -> None:
        raw = (
            "2026-03-21T10:00:00.000Z ##[group]Run python -c ...\n"
            "2026-03-21T10:00:01.000Z \x1b[31mTraceback (most recent call last):\x1b[0m\n"
            "2026-03-21T10:00:01.200Z ModuleNotFoundError: No module named 'foo'\n"
            "2026-03-21T10:00:01.300Z ##[endgroup]\n"
        )
        lines = clean_real_log(raw)
        assert "Traceback (most recent call last):" in lines
        assert "ModuleNotFoundError: No module named 'foo'" in lines
        assert not any("\x1b" in l for l in lines)
        assert not any("##[" in l for l in lines)
        assert not any("2026-03-21T" in l for l in lines)


# ── extract_failure_window ─────────────────────────────────────────────────────

class TestExtractFailureWindow:
    def _make_lines(self, n: int = 50) -> list[str]:
        return [f"line {i}" for i in range(n)]

    def test_finds_error_marker_and_returns_window(self) -> None:
        lines = self._make_lines(50)
        lines[25] = "ERROR: something broke"
        window = extract_failure_window(lines, n=10)
        assert any("ERROR" in l for l in window)

    def test_finds_traceback_marker(self) -> None:
        lines = self._make_lines(30)
        lines[20] = "Traceback (most recent call last):"
        window = extract_failure_window(lines, n=10)
        assert any("Traceback" in l for l in window)

    def test_finds_failed_marker(self) -> None:
        lines = self._make_lines(30)
        lines[15] = "FAILED tests/test_foo.py::test_bar"
        window = extract_failure_window(lines, n=10)
        assert any("FAILED" in l for l in window)

    def test_fallback_to_last_n_when_no_marker(self) -> None:
        lines = [f"normal line {i}" for i in range(40)]
        window = extract_failure_window(lines, n=10)
        assert window == lines[-10:]

    def test_correct_line_count_returned(self) -> None:
        lines = self._make_lines(100)
        lines[50] = "ERROR: at midpoint"
        window = extract_failure_window(lines, n=10)
        assert len(window) <= 10

    def test_window_does_not_exceed_list_bounds(self) -> None:
        lines = ["ERROR: right at start"] + [f"line {i}" for i in range(5)]
        window = extract_failure_window(lines, n=10)
        # Should not crash even if window extends past start/end
        assert len(window) <= len(lines)

    def test_uses_last_error_marker_not_first(self) -> None:
        lines = self._make_lines(60)
        lines[10] = "ERROR: first error"
        lines[40] = "ERROR: last error"
        window = extract_failure_window(lines, n=10)
        # Window should be centered around line 40, not line 10
        assert any("last error" in l for l in window)

    def test_fallback_line_count_matches_n(self) -> None:
        lines = [f"clean line {i}" for i in range(50)]
        window = extract_failure_window(lines, n=20)
        assert window == lines[-20:]
