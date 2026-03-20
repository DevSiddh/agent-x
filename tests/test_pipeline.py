"""
tests/test_pipeline.py
Step 7 — phase2/pipeline.py
Tests use mocked DeepSeek — no real API calls.
conftest.py guarantees fixture repos are initialised.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase2.memory.store as mem_store
from phase2.memory.store import MemoryEntry
from phase2.pipeline import JSONL_PATH, run

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_DIFF = (
    "--- a/requirements.txt\n"
    "+++ b/requirements.txt\n"
    "@@ -1,2 +1,3 @@\n"
    " requests==2.31.0\n"
    "+setuptools\n"
    " python-dotenv==1.0.0"
)


def _mock_llm(diff: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = diff
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.fixture(autouse=True)
def patch_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect memory writes to temp file — don't pollute real memory.jsonl."""
    tmp_file = tmp_path / "memory.jsonl"
    monkeypatch.setattr(mem_store, "_memory_path", lambda: tmp_file)
    return tmp_file


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPipelineRun:

    def test_single_case_returns_memory_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
            mock_openai.return_value = client

            entry = run("syn_001")

        assert isinstance(entry, MemoryEntry)
        assert entry.run_id != ""
        assert entry.repo == "synthetic"

    def test_memory_always_written(
        self, monkeypatch: pytest.MonkeyPatch, patch_memory: Path
    ) -> None:
        """P8 — memory must be written even when pipeline raises."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
            mock_openai.return_value = client

            # Even on exception, finally block must write
            with patch("phase2.pipeline.classify", side_effect=RuntimeError("boom")):
                entry = run("syn_001")

        assert patch_memory.exists(), "memory.jsonl must exist after run"
        lines = patch_memory.read_text().strip().splitlines()
        assert len(lines) >= 1, "at least one entry must be written"
        data = json.loads(lines[-1])
        assert data["decision"] == "abstained"
        assert "boom" in data["error"]

    def test_observer_mode_when_low_confidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        from phase2.classifier.regex_pass import ClassifierResult
        low_conf = ClassifierResult(
            category="DependencyError",
            confidence=0.30,  # below 0.85 threshold
            matched_pattern="test",
            keyword="test",
            affected_file="requirements.txt",
            bug_signature="synthetic:DependencyError:test:requirements.txt",
        )

        with patch("phase2.pipeline.classify", return_value=low_conf):
            entry = run("syn_001")

        assert entry.mode == "observer"
        assert entry.decision == "abstained"

    def test_decision_set_on_successful_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
            mock_openai.return_value = client

            entry = run("syn_001")

        assert entry.decision in {"accepted", "rejected", "escalated", "abstained"}

    def test_failure_category_populated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
            mock_openai.return_value = client

            entry = run("syn_001")

        assert entry.failure_category == "DependencyError"

    def test_confidence_score_populated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
            mock_openai.return_value = client

            entry = run("syn_001")

        assert entry.confidence_score > 0

    def test_all_5_cases_produce_memory_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All 5 synthetic cases must produce a MemoryEntry without crashing."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with open(JSONL_PATH) as f:
            case_ids = [json.loads(l)["id"] for l in f if l.strip()]

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
            mock_openai.return_value = client

            entries = [run(cid) for cid in case_ids]

        assert len(entries) == 5
        assert all(isinstance(e, MemoryEntry) for e in entries)

    def test_reasoner_enriches_context_before_deepseek(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reasoner is called between build_context and generate_patch."""
        import phase2.pipeline as pl_mod
        from agent_y.reasoner import ReasonerOutput

        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        mock_output = ReasonerOutput(
            action="repair",
            reasoning="setuptools is missing",
            strategy="install missing dependency package via requirements.txt",
            confidence=0.9,
            files_to_change=["requirements.txt"],
        )

        captured_context: list[str] = []

        def fake_generate_patch(error_lines, classifier_result, context):
            captured_context.append(context)
            return pl_mod.generate_patch.__wrapped__(
                error_lines, classifier_result, context
            ) if hasattr(pl_mod.generate_patch, "__wrapped__") else MagicMock(
                diff=VALID_DIFF,
                model_used="deepseek-chat",
                attempt=1,
                sanitiser_result=MagicMock(line_count=3),
            )

        with patch("phase2.pipeline.reason", return_value=mock_output):
            with patch("phase2.pipeline.generate_patch") as mock_gen:
                mock_gen.return_value = MagicMock(
                    diff=VALID_DIFF,
                    model_used="deepseek-chat",
                    attempt=1,
                    sanitiser_result=MagicMock(line_count=3, passed=True),
                )
                with patch("openai.OpenAI") as mock_openai:
                    client = MagicMock()
                    client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
                    mock_openai.return_value = client
                    run("syn_001")

            # Verify generate_patch was called with enriched context (has STRATEGY: prefix)
            call_kwargs = mock_gen.call_args
            passed_context = call_kwargs.kwargs.get("context") or call_kwargs.args[2]
            assert "STRATEGY:" in passed_context
            assert mock_output.strategy in passed_context

    def test_reasoner_error_caught_pipeline_continues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ReasonerError must be caught — pipeline continues with raw context (P5)."""
        from agent_y.reasoner import ReasonerError

        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

        with patch("phase2.pipeline.reason", side_effect=ReasonerError("mock failure")):
            with patch("phase2.pipeline.generate_patch") as mock_gen:
                mock_gen.return_value = MagicMock(
                    diff=VALID_DIFF,
                    model_used="deepseek-chat",
                    attempt=1,
                    sanitiser_result=MagicMock(line_count=3, passed=True),
                )
                with patch("openai.OpenAI") as mock_openai:
                    client = MagicMock()
                    client.chat.completions.create.return_value = _mock_llm(VALID_DIFF)
                    mock_openai.return_value = client
                    entry = run("syn_001")

        # Pipeline must complete — not crash — when Reasoner fails
        assert isinstance(entry, MemoryEntry)
        assert entry.decision in {"accepted", "rejected", "escalated", "abstained"}
        # generate_patch must still have been called (fallback to raw context)
        assert mock_gen.called
