"""
tests/test_patch_gen.py
Step 4 — phase2/patch_gen/sanitiser.py + worker.py
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.classifier.regex_pass import ClassifierResult
from phase2.patch_gen.sanitiser import (
    SanitiserResult,
    count_diff_lines,
    strip_markdown_fences,
    validate_patch,
)
from phase2.patch_gen.worker import MAX_RETRIES, generate_patch

# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_DIFF = (
    "--- a/requirements.txt\n"
    "+++ b/requirements.txt\n"
    "@@ -1,2 +1,3 @@\n"
    " requests==2.31.0\n"
    "+setuptools\n"
    " python-dotenv==1.0.0"
)

DUMMY_CLASSIFIER = ClassifierResult(
    category="DependencyError",
    confidence=0.99,
    matched_pattern="ModuleNotFoundError",
    keyword="pkg_resources",
    affected_file="requirements.txt",
    bug_signature="test/repo:DependencyError:pkg_resources:requirements.txt",
)


def _mock_llm(response_text: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = response_text
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ── strip_markdown_fences ─────────────────────────────────────────────────────

class TestStripMarkdownFences:

    def test_removes_diff_fence(self) -> None:
        fenced = "```diff\n--- a/foo\n+++ b/foo\n@@ -1 +1 @@\n-old\n+new\n```"
        result = strip_markdown_fences(fenced)
        assert result.startswith("---")
        assert "```" not in result

    def test_removes_generic_fence(self) -> None:
        fenced = "```\n--- a/foo\n+++ b/foo\n-old\n+new\n```"
        result = strip_markdown_fences(fenced)
        assert result.startswith("---")

    def test_already_clean_diff_unchanged(self) -> None:
        result = strip_markdown_fences(VALID_DIFF)
        assert result == VALID_DIFF

    def test_finds_diff_start_after_preamble(self) -> None:
        text = "Here is the fix:\n\n--- a/foo\n+++ b/foo\n-old\n+new"
        result = strip_markdown_fences(text)
        assert result.startswith("---")

    def test_returns_text_if_no_diff_header(self) -> None:
        result = strip_markdown_fences("just some text with no diff")
        assert result == "just some text with no diff"


# ── count_diff_lines ─────────────────────────────────────────────────────────

class TestCountDiffLines:

    def test_counts_added_and_removed(self) -> None:
        diff = "--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new"
        assert count_diff_lines(diff) == 2

    def test_ignores_headers(self) -> None:
        diff = "--- a/f\n+++ b/f\n@@ -1 +1 @@\n+new"
        assert count_diff_lines(diff) == 1

    def test_counts_only_changed_lines(self) -> None:
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,4 @@\n context\n-old\n+new1\n+new2"
        assert count_diff_lines(diff) == 3

    def test_empty_diff_returns_zero(self) -> None:
        assert count_diff_lines("") == 0


# ── validate_patch ────────────────────────────────────────────────────────────

class TestValidatePatch:

    def test_accepts_valid_diff(self) -> None:
        r = validate_patch(VALID_DIFF)
        assert r.passed is True
        assert r.line_count == 1
        assert r.rejection_reason == ""

    def test_rejects_non_diff_text(self) -> None:
        r = validate_patch("This is just some text")
        assert r.passed is False
        assert "---" in r.rejection_reason

    def test_rejects_over_15_lines(self) -> None:
        big = "--- a/f\n+++ b/f\n@@ -1 +1 @@\n" + "\n".join(f"+line{i}" for i in range(16))
        r = validate_patch(big)
        assert r.passed is False
        assert r.line_count == 16
        assert "15" in r.rejection_reason

    def test_accepts_exactly_15_lines(self) -> None:
        diff = "--- a/f\n+++ b/f\n@@ -1 +1 @@\n" + "\n".join(f"+line{i}" for i in range(15))
        r = validate_patch(diff)
        assert r.passed is True
        assert r.line_count == 15

    def test_strips_fences_before_validating(self) -> None:
        fenced = "```diff\n" + VALID_DIFF + "\n```"
        r = validate_patch(fenced)
        assert r.passed is True

    def test_returns_sanitiser_result_model(self) -> None:
        r = validate_patch(VALID_DIFF)
        assert isinstance(r, SanitiserResult)


# ── generate_patch (worker) ───────────────────────────────────────────────────

class TestGeneratePatch:

    def test_returns_valid_result_on_first_attempt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
            mock_openai.return_value = client

            result = generate_patch(
                error_lines=["ModuleNotFoundError: No module named 'pkg_resources'"],
                classifier_result=DUMMY_CLASSIFIER,
                context="requests==2.31.0\npython-dotenv==1.0.0\n",
            )

        assert result.attempt == 1
        assert result.diff.startswith("---")
        assert result.sanitiser_result.passed is True

    def test_retry_uses_different_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P11 — retry prompt must differ from initial (includes rejection_reason)."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        bad = "not a diff at all"  # will be rejected
        good = VALID_DIFF

        responses = [_mock_llm(bad), _mock_llm(good)]

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.side_effect = responses
            mock_openai.return_value = client

            result = generate_patch(
                error_lines=["ModuleNotFoundError"],
                classifier_result=DUMMY_CLASSIFIER,
                context="requests==2.31.0\n",
            )

        assert result.attempt == 2

        # Verify retry prompt contained rejection context
        calls = client.chat.completions.create.call_args_list
        retry_messages = calls[1][1]["messages"]
        user_prompt = next(m["content"] for m in retry_messages if m["role"] == "user")
        assert "REJECTED" in user_prompt
        assert "Reason:" in user_prompt

    def test_respects_max_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            # Always return bad response
            client.chat.completions.create.return_value = _mock_llm("not a diff")
            mock_openai.return_value = client

            with pytest.raises(RuntimeError, match="exhausted"):
                generate_patch(
                    error_lines=["error"],
                    classifier_result=DUMMY_CLASSIFIER,
                    context="content",
                )

        assert client.chat.completions.create.call_count == MAX_RETRIES

    def test_raises_when_api_key_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="DEEPSEEK_API_KEY"):
            generate_patch(
                error_lines=["error"],
                classifier_result=DUMMY_CLASSIFIER,
                context="content",
            )

    def test_system_prompt_contains_format_example(self) -> None:
        """System prompt must show exact --- a/ +++ b/ format so LLM knows."""
        from phase2.patch_gen.worker import SYSTEM_PROMPT
        assert "--- a/" in SYSTEM_PROMPT
        assert "+++ b/" in SYSTEM_PROMPT

    def test_retry_prompt_contains_format_reminder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """P11 — retry prompt must include format reminder with exact path."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        bad = "--- a/requirements.txt\n@@ -1 +1 @@\n+setuptools"  # missing +++
        good = VALID_DIFF
        responses = [_mock_llm(bad), _mock_llm(good)]

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.side_effect = responses
            mock_openai.return_value = client

            generate_patch(
                error_lines=["ModuleNotFoundError"],
                classifier_result=DUMMY_CLASSIFIER,
                context="content",
            )

        calls = client.chat.completions.create.call_args_list
        retry_user = next(
            m["content"]
            for m in calls[1][1]["messages"]
            if m["role"] == "user"
        )
        assert "REJECTED" in retry_user
        assert "REQUIRED FORMAT REMINDER" in retry_user
        assert "+++ b/" in retry_user


# ── sanitiser path + header checks ───────────────────────────────────────────

class TestValidatePatchExtended:

    def test_rejects_missing_plus_header(self) -> None:
        """syn_002 pattern — DeepSeek omits the +++ b/ line."""
        diff_no_plus = "--- a/Makefile\n@@ -3,1 +3,1 @@\n-old\n+new"
        r = validate_patch(diff_no_plus)
        assert r.passed is False
        assert "+++" in r.rejection_reason

    def test_accepts_diff_with_plus_header(self) -> None:
        diff = "--- a/Makefile\n+++ b/Makefile\n@@ -3,1 +3,1 @@\n-old\n+new"
        r = validate_patch(diff)
        assert r.passed is True

    def test_rejects_wrong_file_path(self) -> None:
        """syn_004 pattern — DeepSeek uses wrong path in diff header."""
        diff = "--- a/schemas.py\n+++ b/schemas.py\n@@ -1 +1 @@\n+fix"
        r = validate_patch(diff, affected_file="app/schemas.py")
        assert r.passed is False
        assert "app/schemas.py" in r.rejection_reason

    def test_accepts_correct_file_path(self) -> None:
        diff = "--- a/app/schemas.py\n+++ b/app/schemas.py\n@@ -1 +1 @@\n+fix"
        r = validate_patch(diff, affected_file="app/schemas.py")
        assert r.passed is True

    def test_no_path_check_when_affected_file_empty(self) -> None:
        """When no affected_file provided, path check is skipped."""
        diff = "--- a/anything.py\n+++ b/anything.py\n@@ -1 +1 @@\n+fix"
        r = validate_patch(diff, affected_file="")
        assert r.passed is True
