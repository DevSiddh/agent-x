"""
tests/test_reasoner.py
Tests for agent_y/reasoner.py — reasoning layer for Agent-X.
Mocks all DeepSeek API calls — no real HTTP in tests.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agent_y.reasoner import (
    MAX_RETRIES,
    ReasonerError,
    ReasonerOutput,
    _extract_json,
    _filter_files,
    reason,
    validate_strategy,
)
from phase2.classifier.regex_pass import ClassifierResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_classification(
    category: str = "DependencyError",
    affected_file: str = "requirements.txt",
) -> ClassifierResult:
    return ClassifierResult(
        category=category,
        confidence=0.99,
        matched_pattern=r"ModuleNotFoundError",
        keyword="pkg_resources",
        affected_file=affected_file,
        bug_signature=f"repo:test:{category}:pkg_resources:{affected_file}",
    )


def make_valid_json(
    action: str = "repair",
    strategy: str = "install the missing dependency package",
    confidence: float = 0.9,
    files: list | None = None,
) -> str:
    return json.dumps({
        "action": action,
        "reasoning": "The error indicates a missing package.",
        "strategy": strategy,
        "confidence": confidence,
        "files_to_change": files or ["requirements.txt"],
        "diagnosis": "Missing package caused import to fail at runtime.",
    })


def make_mock_client(content: str) -> MagicMock:
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ---------------------------------------------------------------------------
# ReasonerOutput model validation
# ---------------------------------------------------------------------------


class TestReasonerOutputModel:
    def test_valid_output_accepted(self) -> None:
        out = ReasonerOutput(
            action="repair",
            reasoning="test reason",
            strategy="install missing package",
            confidence=0.9,
            files_to_change=["requirements.txt"],
        )
        assert out.action == "repair"
        assert out.confidence == 0.9

    def test_invalid_action_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasonerOutput(
                action="delete",  # type: ignore[arg-type]
                reasoning="r",
                strategy="install something",
                confidence=0.5,
                files_to_change=[],
            )

    def test_more_than_three_files_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasonerOutput(
                action="repair",
                reasoning="r",
                strategy="install something",
                confidence=0.5,
                files_to_change=["a.py", "b.py", "c.py", "d.py"],
            )

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasonerOutput(
                action="repair",
                reasoning="r",
                strategy="install something",
                confidence=1.5,
                files_to_change=[],
            )

    def test_empty_strategy_rejected(self) -> None:
        with pytest.raises(Exception):
            ReasonerOutput(
                action="repair",
                reasoning="r",
                strategy="",
                confidence=0.5,
                files_to_change=[],
            )


# ---------------------------------------------------------------------------
# validate_strategy
# ---------------------------------------------------------------------------


class TestValidateStrategy:
    def test_matching_dependency_error(self) -> None:
        assert validate_strategy("install the missing package dependency", "DependencyError") is True

    def test_matching_config_error(self) -> None:
        assert validate_strategy("add missing import before create_all", "ConfigError") is True

    def test_matching_runtime_error(self) -> None:
        assert validate_strategy("resolve pydantic model namespace conflict", "RuntimeError") is True

    def test_mismatched_category_returns_false(self) -> None:
        # DependencyError strategy that mentions renaming — no dependency keywords
        assert validate_strategy("rename the variable to fix the issue", "DependencyError") is False

    def test_unknown_category_returns_false(self) -> None:
        assert validate_strategy("do something", "UnknownCategory") is False

    def test_case_insensitive(self) -> None:
        assert validate_strategy("Install the PACKAGE from requirements", "DependencyError") is True


# ---------------------------------------------------------------------------
# _filter_files
# ---------------------------------------------------------------------------


class TestFilterFiles:
    def test_keeps_affected_file(self) -> None:
        result = _filter_files(["requirements.txt"], "requirements.txt", "requirements.txt")
        assert result == ["requirements.txt"]

    def test_removes_unrelated_files(self) -> None:
        result = _filter_files(
            ["requirements.txt", "unrelated.py"],
            "Error in requirements.txt",
            "requirements.txt",
        )
        assert "unrelated.py" not in result

    def test_hard_cap_at_three(self) -> None:
        files = ["a.py", "b.py", "c.py", "d.py"]
        context = "a.py b.py c.py d.py"
        result = _filter_files(files, context, "a.py")
        assert len(result) <= 3

    def test_fallback_to_affected_file_when_no_match(self) -> None:
        result = _filter_files(["totally_unrelated.py"], "error in requirements.txt", "requirements.txt")
        assert "requirements.txt" in result

    def test_empty_files_list(self) -> None:
        result = _filter_files([], "context", "requirements.txt")
        assert result == []


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_clean_json_parsed(self) -> None:
        raw = '{"action": "repair", "strategy": "fix it"}'
        result = _extract_json(raw)
        assert result["action"] == "repair"

    def test_fenced_json_parsed(self) -> None:
        raw = '```json\n{"action": "repair", "strategy": "fix it"}\n```'
        result = _extract_json(raw)
        assert result["action"] == "repair"

    def test_json_with_preamble_parsed(self) -> None:
        raw = 'Here is the JSON:\n{"action": "repair", "strategy": "fix it"}'
        result = _extract_json(raw)
        assert result["action"] == "repair"

    def test_no_json_raises(self) -> None:
        import json as _json
        with pytest.raises(_json.JSONDecodeError):
            _extract_json("no json here at all")


# ---------------------------------------------------------------------------
# reason() — happy path
# ---------------------------------------------------------------------------


class TestReasonHappyPath:
    def test_returns_reasoner_output_on_valid_response(self) -> None:
        cls = make_classification()
        client = make_mock_client(make_valid_json())
        context = "Error in requirements.txt\nModuleNotFoundError: pkg_resources"

        with patch("agent_y.reasoner.OpenAI", return_value=client):
            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
                output = reason(context, cls)

        assert isinstance(output, ReasonerOutput)
        assert output.action == "repair"
        assert output.confidence == 0.9

    def test_api_called_once_on_success(self) -> None:
        cls = make_classification()
        client = make_mock_client(make_valid_json())
        context = "Error in requirements.txt"

        with patch("agent_y.reasoner.OpenAI", return_value=client):
            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
                reason(context, cls)

        assert client.chat.completions.create.call_count == 1

    def test_confidence_stored_not_used_in_decisions(self) -> None:
        """confidence is in output but no branching on it inside reason()."""
        import inspect
        import ast

        import agent_y.reasoner as mod
        source = inspect.getsource(mod.reason)
        tree = ast.parse(source)

        # Check that 'confidence' never appears as a condition in an If node
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                condition_src = ast.unparse(node.test)
                assert "confidence" not in condition_src, (
                    f"confidence used in branching logic: {condition_src}"
                )


# ---------------------------------------------------------------------------
# reason() — retry behaviour
# ---------------------------------------------------------------------------


class TestReasonRetry:
    def test_retries_on_json_parse_failure(self) -> None:
        cls = make_classification()
        context = "Error in requirements.txt"

        bad_response = MagicMock()
        bad_response.message.content = "not json at all"

        good_response = MagicMock()
        good_response.message.content = make_valid_json()

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[bad_response]),
            MagicMock(choices=[good_response]),
        ]

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client):
            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
                output = reason(context, cls)

        assert mock_client.chat.completions.create.call_count == 2
        assert isinstance(output, ReasonerOutput)

    def test_retry_prompt_differs_from_initial(self) -> None:
        """Verify retry prompt includes error context — not an identical retry."""
        cls = make_classification()
        context = "Error in requirements.txt"

        bad_response = MagicMock()
        bad_response.message.content = "garbage"

        good_response = MagicMock()
        good_response.message.content = make_valid_json()

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[bad_response]),
            MagicMock(choices=[good_response]),
        ]

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client):
            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
                reason(context, cls)

        calls = mock_client.chat.completions.create.call_args_list
        first_user = calls[0].kwargs["messages"][-1]["content"]
        second_user = calls[1].kwargs["messages"][-1]["content"]
        assert first_user != second_user
        assert "FAILED" in second_user or "error" in second_user.lower()

    def test_raises_reasoner_error_after_max_retries(self) -> None:
        cls = make_classification()
        context = "Error in requirements.txt"

        bad_response = MagicMock()
        bad_response.message.content = "not json"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[bad_response]
        )

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client):
            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
                with pytest.raises(ReasonerError):
                    reason(context, cls)

        assert mock_client.chat.completions.create.call_count == MAX_RETRIES + 1

    def test_raises_reasoner_error_on_strategy_mismatch_after_retries(self) -> None:
        """Strategy that doesn't match category → treated as failure → ReasonerError."""
        cls = make_classification(category="DependencyError")
        context = "Error in requirements.txt"

        # Returns valid JSON but strategy has no dependency keywords
        bad_strategy_json = json.dumps({
            "action": "repair",
            "reasoning": "something",
            "strategy": "rename the variable to snake_case",
            "confidence": 0.8,
            "files_to_change": ["requirements.txt"],
            "diagnosis": "Wrong variable name used.",
        })

        mock_client = make_mock_client(bad_strategy_json)

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client):
            with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
                with pytest.raises(ReasonerError):
                    reason(context, cls)
