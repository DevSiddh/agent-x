"""
tests/test_fetcher.py
Step 2 — phase1/log_fetcher/fetcher.py
Tests: lazy token, ZIP sort order, line extraction, window size, HTTP mocking.
"""
import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase1.log_fetcher.fetcher import _extract_log_lines, _get_token, fetch_logs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_zip(files: dict[str, str]) -> bytes:
    """Build an in-memory ZIP from a dict of {filename: content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _mock_response(zip_bytes: bytes) -> MagicMock:
    mock = MagicMock()
    mock.content = zip_bytes
    mock.raise_for_status = MagicMock()
    return mock


# ── _get_token ─────────────────────────────────────────────────────────────────

class TestGetToken:

    def test_returns_token_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
        assert _get_token() == "ghp_testtoken"

    def test_raises_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(EnvironmentError, match="GITHUB_TOKEN is not set"):
            _get_token()

    def test_raises_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "")
        with pytest.raises(EnvironmentError):
            _get_token()


# ── _extract_log_lines ────────────────────────────────────────────────────────

class TestExtractLogLines:

    def test_extracts_lines_from_zip(self) -> None:
        zip_bytes = _make_zip({"1_Setup.txt": "line one\nline two\n"})
        result = _extract_log_lines(zip_bytes)
        assert result == ["line one", "line two"]

    def test_zip_files_processed_in_sorted_order(self) -> None:
        """P9 — files must be sorted so step logs come in correct sequence."""
        zip_bytes = _make_zip({
            "3_Deploy.txt": "deploy\n",
            "1_Setup.txt": "setup\n",
            "2_Build.txt": "build\n",
        })
        result = _extract_log_lines(zip_bytes)
        assert result == ["setup", "build", "deploy"], \
            f"Expected sorted order, got: {result}"

    def test_skips_non_txt_files(self) -> None:
        zip_bytes = _make_zip({
            "1_Setup.txt": "log line\n",
            "meta.json": '{"key": "value"}',
        })
        result = _extract_log_lines(zip_bytes)
        assert result == ["log line"]

    def test_returns_empty_on_bad_zip(self) -> None:
        result = _extract_log_lines(b"this is not a zip")
        assert result == []

    def test_handles_multiple_files(self) -> None:
        zip_bytes = _make_zip({
            "1_Setup.txt": "setup1\nsetup2\n",
            "2_Build.txt": "build1\nbuild2\n",
        })
        result = _extract_log_lines(zip_bytes)
        assert len(result) == 4
        assert result[0] == "setup1"
        assert result[-1] == "build2"


# ── fetch_logs ────────────────────────────────────────────────────────────────

class TestFetchLogs:

    def test_returns_last_n_lines(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        monkeypatch.setenv("ERROR_WINDOW_LINES", "2")

        lines = [f"line {i}\n" for i in range(10)]
        zip_bytes = _make_zip({"1_log.txt": "".join(lines)})

        with patch("phase1.log_fetcher.fetcher.requests.get",
                   return_value=_mock_response(zip_bytes)):
            result = fetch_logs("https://fake/logs", run_id=1)

        assert result == ["line 8", "line 9"]

    def test_raises_when_token_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(EnvironmentError):
            fetch_logs("https://fake/logs", run_id=1)

    def test_returns_empty_on_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        import requests as req
        mock = MagicMock()
        mock.raise_for_status.side_effect = req.HTTPError("404")

        with patch("phase1.log_fetcher.fetcher.requests.get", return_value=mock):
            result = fetch_logs("https://fake/logs", run_id=1)

        assert result == []

    def test_returns_empty_on_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        import requests as req

        with patch("phase1.log_fetcher.fetcher.requests.get",
                   side_effect=req.Timeout):
            result = fetch_logs("https://fake/logs", run_id=1)

        assert result == []

    def test_no_real_http_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify requests.get is always mocked — no real network calls."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        zip_bytes = _make_zip({"1_log.txt": "line\n"})

        with patch("phase1.log_fetcher.fetcher.requests.get",
                   return_value=_mock_response(zip_bytes)) as mock_get:
            fetch_logs("https://fake/logs", run_id=99)
            mock_get.assert_called_once()
