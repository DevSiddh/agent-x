"""
tests/test_github_file.py
Tests for phase2/tools/github_file.py — GitHub file fetcher.
All HTTP calls are mocked — no real network requests.
"""
import base64
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.tools.github_file import extract_relative_path, fetch_file


# ---------------------------------------------------------------------------
# extract_relative_path
# ---------------------------------------------------------------------------

class TestExtractRelativePath:

    def test_standard_runner_path(self) -> None:
        path = "/home/runner/work/my-repo/my-repo/src/main.py"
        assert extract_relative_path(path) == "src/main.py"

    def test_root_level_file(self) -> None:
        path = "/home/runner/work/-agent-x-test-repo/-agent-x-test-repo/main.py"
        assert extract_relative_path(path) == "main.py"

    def test_nested_path(self) -> None:
        path = "/home/runner/work/org-repo/org-repo/a/b/c/deep.py"
        assert extract_relative_path(path) == "a/b/c/deep.py"

    def test_non_runner_path_returns_none(self) -> None:
        assert extract_relative_path("requirements.txt") is None

    def test_local_absolute_path_returns_none(self) -> None:
        assert extract_relative_path("/home/user/projects/app/main.py") is None

    def test_empty_string_returns_none(self) -> None:
        assert extract_relative_path("") is None


# ---------------------------------------------------------------------------
# fetch_file
# ---------------------------------------------------------------------------

class TestFetchFile:

    def _make_response(self, content: str, status_code: int = 200) -> MagicMock:
        """Build a mock requests.Response with base64-encoded content."""
        encoded = base64.b64encode(content.encode()).decode()
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = {"content": encoded}
        resp.raise_for_status = MagicMock()
        return resp

    def test_returns_content_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok-test")
        expected = "print('hello')\n"
        mock_resp = self._make_response(expected)

        with patch("requests.get", return_value=mock_resp):
            result = fetch_file("owner/repo", "main.py")

        assert result == expected

    def test_returns_none_on_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok-test")
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("requests.get", return_value=mock_resp):
            result = fetch_file("owner/repo", "missing.py")

        assert result is None

    def test_returns_none_when_no_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        result = fetch_file("owner/repo", "main.py")
        assert result is None

    def test_returns_none_on_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok-test")

        with patch("requests.get", side_effect=ConnectionError("timeout")):
            result = fetch_file("owner/repo", "main.py")

        assert result is None

    def test_uses_ref_in_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok-test")
        mock_resp = self._make_response("content")

        with patch("requests.get", return_value=mock_resp) as mock_get:
            fetch_file("owner/repo", "main.py", ref="abc123")

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
        # params may be in kwargs
        if not params:
            params = call_kwargs.kwargs.get("params", {})
        assert params.get("ref") == "abc123"

    def test_never_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fetch_file must never raise — any exception → None."""
        monkeypatch.setenv("GITHUB_TOKEN", "tok-test")

        with patch("requests.get", side_effect=RuntimeError("unexpected")):
            result = fetch_file("owner/repo", "main.py")

        assert result is None


# ---------------------------------------------------------------------------
# context_builder integration (P23 fix)
# ---------------------------------------------------------------------------

class TestContextBuilderP23:
    """Verify context_builder uses fetch_file when local file is missing."""

    def test_fetches_from_github_when_local_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If affected_file is a runner path, content fetched from GitHub API."""
        monkeypatch.setenv("GITHUB_TOKEN", "tok-test")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "x")

        from phase2.classifier.regex_pass import ClassifierResult
        from phase2.memory.similarity import MemoryEngine

        runner_path = "/home/runner/work/owner-repo/owner-repo/main.py"
        result = ClassifierResult(
            category="DependencyError",
            confidence=0.99,
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file=runner_path,
            bug_signature="owner/repo:DependencyError:pkg_resources:main.py",
        )

        fetched_content = "import pkg_resources\n"

        with patch("phase2.context_builder.fetch_file", return_value=fetched_content) as mock_fetch:
            with patch.object(MemoryEngine, "find_for_rag", return_value=[]):
                from phase2.context_builder import build_context
                ctx = build_context(
                    classifier_result=result,
                    fixture_path=tmp_path,  # empty → local file missing
                    error_lines=["ModuleNotFoundError: No module named 'pkg_resources'"],
                )

        assert fetched_content in ctx
        mock_fetch.assert_called_once_with("owner/repo", "main.py")

    def test_falls_back_to_not_found_when_fetch_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "tok-test")

        from phase2.classifier.regex_pass import ClassifierResult
        from phase2.memory.similarity import MemoryEngine

        runner_path = "/home/runner/work/owner-repo/owner-repo/main.py"
        result = ClassifierResult(
            category="DependencyError",
            confidence=0.99,
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file=runner_path,
            bug_signature="owner/repo:DependencyError:pkg_resources:main.py",
        )

        with patch("phase2.context_builder.fetch_file", return_value=None):
            with patch.object(MemoryEngine, "find_for_rag", return_value=[]):
                from phase2.context_builder import build_context
                ctx = build_context(
                    classifier_result=result,
                    fixture_path=tmp_path,
                    error_lines=[],
                )

        assert "File not found in fixture" in ctx

    def test_local_file_takes_priority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If local file exists, GitHub API must NOT be called."""
        monkeypatch.setenv("GITHUB_TOKEN", "tok-test")

        (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")

        from phase2.classifier.regex_pass import ClassifierResult
        from phase2.memory.similarity import MemoryEngine

        result = ClassifierResult(
            category="DependencyError",
            confidence=0.99,
            matched_pattern="ModuleNotFoundError",
            keyword="setuptools",
            affected_file="requirements.txt",
            bug_signature="owner/repo:DependencyError:setuptools:requirements.txt",
        )

        with patch("phase2.context_builder.fetch_file") as mock_fetch:
            with patch.object(MemoryEngine, "find_for_rag", return_value=[]):
                from phase2.context_builder import build_context
                ctx = build_context(
                    classifier_result=result,
                    fixture_path=tmp_path,
                    error_lines=[],
                )

        mock_fetch.assert_not_called()
        assert "requests==2.31.0" in ctx
