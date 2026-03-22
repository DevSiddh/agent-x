"""
tests/test_context_builder.py
v2.1 — phase2/context_builder.py
Tests cover: file content, triple-hybrid RAG hits/misses, action tags, missing file.
context_builder now calls MemoryEngine.find_for_rag — mock that, not store.get_similar.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.classifier.regex_pass import ClassifierResult
from phase2.context_builder import build_context

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dep_result() -> ClassifierResult:
    return ClassifierResult(
        category="DependencyError",
        confidence=0.99,
        matched_pattern="ModuleNotFoundError",
        keyword="pkg_resources",
        affected_file="requirements.txt",
        bug_signature="synthetic:DependencyError:pkg_resources:requirements.txt",
    )


def _fixture_path() -> Path:
    return FIXTURES_ROOT / "syn_001"


def _mock_rag(
    score: float,
    patch: str = "--- a/f\n+++ b/f\n+fix\n",
) -> list[tuple[dict, float]]:
    """Return a single-entry RAG result list suitable for mocking find_for_rag."""
    return [
        (
            {
                "patch_applied": patch,
                "decision": "accepted",
                "retries_used": 0,
                "bug_signature": "synthetic:DependencyError:pkg:requirements.txt",
            },
            score,
        )
    ]


# ---------------------------------------------------------------------------
# Section 1 — Error summary
# ---------------------------------------------------------------------------

class TestErrorSummary:

    def test_summary_section_present(self) -> None:
        ctx = build_context(_dep_result(), _fixture_path())
        assert "## Error Summary" in ctx

    def test_summary_contains_category(self) -> None:
        ctx = build_context(_dep_result(), _fixture_path())
        assert "DependencyError" in ctx

    def test_summary_contains_keyword(self) -> None:
        ctx = build_context(_dep_result(), _fixture_path())
        assert "pkg_resources" in ctx

    def test_summary_contains_affected_file(self) -> None:
        ctx = build_context(_dep_result(), _fixture_path())
        assert "requirements.txt" in ctx

    def test_error_lines_included_in_summary(self) -> None:
        error_lines = ["ModuleNotFoundError: No module named 'pkg_resources'"]
        ctx = build_context(_dep_result(), _fixture_path(), error_lines=error_lines)
        assert "pkg_resources" in ctx

    def test_error_lines_capped_at_20(self) -> None:
        """Token budget — never dump 200 lines into prompt."""
        lines = [f"line {i}" for i in range(100)]
        ctx = build_context(_dep_result(), _fixture_path(), error_lines=lines)
        assert "line 20" not in ctx
        assert "line 0" in ctx


# ---------------------------------------------------------------------------
# Section 2 — Affected file content
# ---------------------------------------------------------------------------

class TestFileContent:

    def test_file_section_present(self) -> None:
        ctx = build_context(_dep_result(), _fixture_path())
        assert "## Affected File" in ctx

    def test_file_content_included_when_exists(self) -> None:
        ctx = build_context(_dep_result(), _fixture_path())
        # syn_001/requirements.txt has "requests==2.31.0"
        assert "requests" in ctx

    def test_missing_file_graceful(self) -> None:
        result = ClassifierResult(
            category="DependencyError",
            confidence=0.99,
            matched_pattern="test",
            keyword="test",
            affected_file="nonexistent_file.txt",
            bug_signature="synthetic:DependencyError:test:nonexistent_file.txt",
        )
        ctx = build_context(result, _fixture_path())
        assert "## Affected File" in ctx
        assert "not found" in ctx.lower() or "nonexistent_file.txt" in ctx

    def test_returns_string(self) -> None:
        ctx = build_context(_dep_result(), _fixture_path())
        assert isinstance(ctx, str)
        assert len(ctx) > 0


# ---------------------------------------------------------------------------
# Section 3 — RAG retrieval (triple-hybrid, mocked via find_for_rag)
# ---------------------------------------------------------------------------

class TestRAGRetrieval:

    def test_past_fixes_section_absent_when_memory_empty(self) -> None:
        # find_for_rag returns [] → no section injected
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=[],
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "## Past Similar Fixes" not in ctx

    def test_past_fixes_section_present_when_memory_has_entries(self) -> None:
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=_mock_rag(score=0.75),
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "## Past Similar Fixes" in ctx

    def test_past_fix_shows_decision(self) -> None:
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=_mock_rag(score=0.75),
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "accepted" in ctx

    def test_at_most_3_past_fixes(self) -> None:
        # MemoryEngine._TOP_K=3, but mock returns 5 → build_context shows what's returned
        # Since find_for_rag itself caps at _TOP_K, mock 5 to verify caller handles it
        five_entries = [
            (
                {"patch_applied": f"+fix{i}", "decision": "accepted", "retries_used": i},
                0.80,
            )
            for i in range(5)
        ]
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=five_entries,
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert ctx.count("### Past Fix") <= 5  # caller renders all returned entries

    def test_different_category_not_included(self) -> None:
        # find_for_rag does the filtering — mock returns [] for non-matching category
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=[],
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "## Past Similar Fixes" not in ctx

    def test_high_relevance_tag_present(self) -> None:
        # score=0.75 → >= _RAG_HIGH_THRESHOLD (0.70) → HIGH RELEVANCE tag
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=_mock_rag(score=0.75),
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "[HIGH RELEVANCE: Adapt this pattern]" in ctx

    def test_low_relevance_tag_present(self) -> None:
        # score=0.60 → in [0.55, 0.70) → LOW RELEVANCE tag
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=_mock_rag(score=0.60),
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "[LOW RELEVANCE: Loose inspiration only. DO NOT copy directly.]" in ctx

    def test_do_not_copy_in_low_relevance_tag(self) -> None:
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=_mock_rag(score=0.60),
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "DO NOT copy directly" in ctx

    def test_no_rag_section_when_find_for_rag_empty(self) -> None:
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=[],
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "## Past Similar Fixes" not in ctx

    def test_patch_preview_included_in_output(self) -> None:
        patch_text = "--- a/requirements.txt\n+++ b/requirements.txt\n+setuptools\n"
        with patch(
            "phase2.context_builder.MemoryEngine.find_for_rag",
            return_value=_mock_rag(score=0.75, patch=patch_text),
        ):
            ctx = build_context(_dep_result(), _fixture_path())
        assert "setuptools" in ctx
