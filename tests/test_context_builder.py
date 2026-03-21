"""
tests/test_context_builder.py
Step 9 — phase2/context_builder.py
Tests cover: file content, RAG hits, empty memory, missing file.
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase2.memory.store as mem_store
from phase2.classifier.regex_pass import ClassifierResult
from phase2.context_builder import build_context
from phase2.memory.store import append, build_default_entry

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect memory reads/writes to temp file — never touch real memory.jsonl."""
    tmp_file = tmp_path / "memory.jsonl"
    monkeypatch.setattr(mem_store, "_memory_path", lambda: tmp_file)
    return tmp_file


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
        # line 21 onward should not appear
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
# Section 3 — RAG retrieval
# ---------------------------------------------------------------------------

class TestRAGRetrieval:

    def test_past_fixes_section_absent_when_memory_empty(self) -> None:
        ctx = build_context(_dep_result(), _fixture_path())
        assert "## Past Similar Fixes" not in ctx

    def test_past_fixes_section_present_when_memory_has_entries(
        self, patch_memory: Path
    ) -> None:
        entry = build_default_entry("run-001", "synthetic")
        entry = entry.model_copy(update={
            "failure_category": "DependencyError",
            "bug_signature": "synthetic:DependencyError:pkg_resources:requirements.txt",
            "decision": "accepted",
            "patch_applied": "--- a/requirements.txt\n+++ b/requirements.txt\n@@ -1 +1,2 @@\n+setuptools\n",
        })
        append(entry)

        ctx = build_context(_dep_result(), _fixture_path())
        assert "## Past Similar Fixes" in ctx

    def test_past_fix_shows_decision(self, patch_memory: Path) -> None:
        entry = build_default_entry("run-001", "synthetic")
        entry = entry.model_copy(update={
            "failure_category": "DependencyError",
            "bug_signature": "synthetic:DependencyError:pkg_resources:requirements.txt",
            "decision": "accepted",
            "patch_applied": "--- a/f\n+++ b/f\n@@ -1 +1 @@\n+fix\n",
        })
        append(entry)
        ctx = build_context(_dep_result(), _fixture_path())
        assert "accepted" in ctx

    def test_at_most_5_past_fixes(self, patch_memory: Path) -> None:
        for i in range(8):
            entry = build_default_entry(f"run-{i:03d}", "synthetic")
            entry = entry.model_copy(update={
                "failure_category": "DependencyError",
                "bug_signature": "synthetic:DependencyError:pkg_resources:requirements.txt",
                "decision": "accepted",
                "patch_applied": f"--- a/f\n+++ b/f\n@@ -1 +1 @@\n+fix{i}\n",
            })
            append(entry)
        ctx = build_context(_dep_result(), _fixture_path())
        # Should have at most 5 "Past Fix N" headers (RAG limit)
        assert ctx.count("### Past Fix") <= 5

    def test_different_category_not_included(self, patch_memory: Path) -> None:
        entry = build_default_entry("run-001", "synthetic")
        entry = entry.model_copy(update={
            "failure_category": "ConfigError",
            "bug_signature": "synthetic:ConfigError:no_such_table:app/database.py",
            "decision": "accepted",
            "patch_applied": "--- a/f\n+++ b/f\n",
        })
        append(entry)
        ctx = build_context(_dep_result(), _fixture_path())
        # DependencyError context should not include ConfigError fixes
        assert "## Past Similar Fixes" not in ctx
