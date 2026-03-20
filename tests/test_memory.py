"""
tests/test_memory.py
Step 6 — phase2/memory/store.py
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase2.memory.store as mem_store
from phase2.memory.store import (
    MemoryEntry,
    already_fixed,
    append,
    build_default_entry,
    get_similar,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_memory_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect all memory ops to a temp file — never touch real memory.jsonl."""
    tmp_file = tmp_path / "memory.jsonl"
    monkeypatch.setattr(mem_store, "_memory_path", lambda: tmp_file)
    return tmp_file


def _make_entry(**overrides) -> MemoryEntry:
    base = build_default_entry("run-test", "test/repo")
    return base.model_copy(update=overrides)


# ---------------------------------------------------------------------------
# MemoryEntry schema
# ---------------------------------------------------------------------------

class TestMemoryEntry:

    def test_valid_model(self) -> None:
        entry = build_default_entry("run-001", "test/repo")
        assert isinstance(entry, MemoryEntry)
        assert entry.run_id == "run-001"
        assert entry.repo == "test/repo"
        assert entry.decision == "abstained"

    def test_confidence_bounds(self) -> None:
        """Pydantic v2 validates at construction — use model_validate to trigger."""
        base = build_default_entry("run-001", "test/repo")
        data = base.model_dump()
        data["confidence_score"] = 1.5
        with pytest.raises(Exception):
            MemoryEntry.model_validate(data)

    def test_all_required_fields_present(self) -> None:
        entry = build_default_entry("run-001", "test/repo")
        data = entry.model_dump()
        required = [
            "run_id", "timestamp", "source", "repo", "failure_category",
            "bug_signature", "confidence_score", "mode", "patch_applied",
            "lines_changed", "model_used", "sandbox_result",
            "regression_introduced", "retries_used", "mttr_seconds",
            "decision", "success_count", "fail_count", "error",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_bug_signature_contains_repo(self) -> None:
        entry = build_default_entry("run-001", "my/repo")
        assert "my/repo" in entry.bug_signature


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------

class TestAppend:

    def test_writes_valid_json_line(self, patch_memory_path: Path) -> None:
        entry = build_default_entry("run-001", "test/repo")
        append(entry)
        lines = patch_memory_path.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["run_id"] == "run-001"

    def test_multiple_appends(self, patch_memory_path: Path) -> None:
        append(build_default_entry("run-001", "test/repo"))
        append(build_default_entry("run-002", "test/repo"))
        append(build_default_entry("run-003", "test/repo"))
        lines = patch_memory_path.read_text().strip().splitlines()
        assert len(lines) == 3

    def test_never_raises_on_bad_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """P8 — append must never raise, even with broken file path."""
        # Point to a path inside a file (impossible directory)
        bad_file = Path(tempfile.mktemp())
        bad_file.write_text("I am a file, not a dir")
        monkeypatch.setattr(
            mem_store, "_memory_path",
            lambda: bad_file / "memory.jsonl"  # file-as-directory → will fail
        )
        entry = build_default_entry("run-001", "test/repo")
        append(entry)  # must NOT raise

    def test_entry_is_valid_json(self, patch_memory_path: Path) -> None:
        entry = _make_entry(decision="accepted")
        append(entry)
        raw = patch_memory_path.read_text().strip()
        parsed = json.loads(raw)
        assert parsed["decision"] == "accepted"


# ---------------------------------------------------------------------------
# already_fixed
# ---------------------------------------------------------------------------

class TestAlreadyFixed:

    def test_returns_false_for_empty_store(self) -> None:
        assert already_fixed("repo:DependencyError:pkg:req.txt", "test/repo") is False

    def test_returns_true_for_accepted_entry(self, patch_memory_path: Path) -> None:
        sig = "test/repo:DependencyError:pkg_resources:requirements.txt"
        entry = _make_entry(
            bug_signature=sig,
            repo="test/repo",
            decision="accepted",
        )
        append(entry)
        assert already_fixed(sig, "test/repo") is True

    def test_returns_false_for_rejected_entry(self, patch_memory_path: Path) -> None:
        """Rejected entries don't count as fixed (P6)."""
        sig = "test/repo:DependencyError:pkg_resources:requirements.txt"
        entry = _make_entry(
            bug_signature=sig,
            repo="test/repo",
            decision="rejected",
        )
        append(entry)
        assert already_fixed(sig, "test/repo") is False

    def test_returns_false_for_wrong_repo(self, patch_memory_path: Path) -> None:
        """Accepted fix for different repo must not match (P12)."""
        sig = "test/repo:DependencyError:pkg_resources:requirements.txt"
        entry = _make_entry(
            bug_signature=sig,
            repo="test/repo",
            decision="accepted",
        )
        append(entry)
        assert already_fixed(sig, "other/repo") is False

    def test_returns_false_for_new_signature(self, patch_memory_path: Path) -> None:
        sig = "test/repo:DependencyError:pkg_resources:requirements.txt"
        entry = _make_entry(bug_signature=sig, repo="test/repo", decision="accepted")
        append(entry)
        assert already_fixed("test/repo:ConfigError:other:file.py", "test/repo") is False


# ---------------------------------------------------------------------------
# get_similar
# ---------------------------------------------------------------------------

class TestGetSimilar:

    def test_returns_empty_when_store_empty(self) -> None:
        result = get_similar("test/repo:DependencyError:pkg:req.txt")
        assert result == []

    def test_returns_matching_category_entries(self, patch_memory_path: Path) -> None:
        dep_sig = "test/repo:DependencyError:pkg_resources:requirements.txt"
        cfg_sig = "test/repo:ConfigError:no_such_table:database.py"

        append(_make_entry(failure_category="DependencyError", bug_signature=dep_sig))
        append(_make_entry(failure_category="DependencyError", bug_signature=dep_sig))
        append(_make_entry(failure_category="ConfigError",     bug_signature=cfg_sig))

        result = get_similar(dep_sig, limit=5)
        assert len(result) == 2
        assert all(e.failure_category == "DependencyError" for e in result)

    def test_respects_limit(self, patch_memory_path: Path) -> None:
        sig = "test/repo:DependencyError:pkg_resources:requirements.txt"
        for i in range(5):
            append(_make_entry(
                run_id=f"run-{i}",
                failure_category="DependencyError",
                bug_signature=sig,
            ))
        result = get_similar(sig, limit=3)
        assert len(result) == 3

    def test_returns_list_of_memory_entries(self, patch_memory_path: Path) -> None:
        sig = "test/repo:DependencyError:pkg_resources:requirements.txt"
        append(_make_entry(failure_category="DependencyError", bug_signature=sig))
        result = get_similar(sig)
        assert all(isinstance(e, MemoryEntry) for e in result)
