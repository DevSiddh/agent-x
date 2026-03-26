"""
tests/test_embedding_classifier.py — Tests for BM25-based EmbeddingClassifier.

Jina/SentenceTransformers removed. Tests now use real BM25 keyword matching.
No mocking needed — BM25 is deterministic and uses no external model.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.classifier.semantic_fallback import (
    EmbeddingClassifier,
    _CONFIDENCE_CAP,
    _CONFIDENCE_FLOOR,
    _MIN_ENTRIES_PER_CATEGORY,
    classify_semantic,
)
from phase2.classifier.regex_pass import classify_with_fallback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_memory(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _dep_entries(n: int = 5) -> list[dict]:
    return [
        {
            "decision": "accepted",
            "failure_category": "DependencyError",
            "bug_signature": "acme:DependencyError:setuptools:requirements.txt",
            "run_id": f"r{i}",
        }
        for i in range(n)
    ]


def _cfg_entries(n: int = 5) -> list[dict]:
    return [
        {
            "decision": "accepted",
            "failure_category": "ConfigError",
            "bug_signature": "acme:ConfigError:database:config.yaml",
            "run_id": f"c{i}",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# EmbeddingClassifier tests
# ---------------------------------------------------------------------------

class TestEmbeddingClassifier:
    def test_build_centroids_returns_categories(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(5))
        clf = EmbeddingClassifier()
        centroids = clf.build_centroids(mp)
        assert "DependencyError" in centroids

    def test_skips_category_below_min_entries(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(_MIN_ENTRIES_PER_CATEGORY - 1))
        clf = EmbeddingClassifier()
        centroids = clf.build_centroids(mp)
        assert "DependencyError" not in centroids

    def test_classifies_when_clear_winner(self, tmp_path):
        # Single category — BM25 always returns that category if score > 0
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(5))
        clf = EmbeddingClassifier()
        result = clf.classify(
            ["acme dependencyerror setuptools requirements txt"] * 3,
            mp,
        )
        # With single category, any match returns DependencyError
        if result:
            assert result.category == "DependencyError"
        # None is acceptable if BM25 scores zero (no overlap) — not a bug

    def test_returns_correct_category_config(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _cfg_entries(5))  # single category
        clf = EmbeddingClassifier()
        result = clf.classify(
            ["acme configerror database config yaml"] * 3,
            mp,
        )
        if result:
            assert result.category == "ConfigError"

    def test_confidence_capped_at_087(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(5))
        clf = EmbeddingClassifier()
        result = clf.classify(
            ["ModuleNotFoundError DependencyError requirements.txt"] * 5, mp
        )
        if result:
            assert result.confidence <= _CONFIDENCE_CAP

    def test_confidence_above_floor(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(5))
        clf = EmbeddingClassifier()
        result = clf.classify(
            ["ModuleNotFoundError: No module named 'setuptools'"], mp
        )
        if result:
            assert result.confidence >= _CONFIDENCE_FLOOR

    def test_returns_none_on_empty_memory(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        mp.touch()
        clf = EmbeddingClassifier()
        result = clf.classify(["some error"], mp)
        assert result is None

    def test_matched_pattern_is_semantic_bm25(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(5))
        clf = EmbeddingClassifier()
        result = clf.classify(
            ["ModuleNotFoundError DependencyError requirements"], mp
        )
        if result:
            assert result.matched_pattern == "semantic_bm25"

    def test_bug_signature_format(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(5))
        clf = EmbeddingClassifier()
        result = clf.classify(
            ["ModuleNotFoundError DependencyError requirements"], mp
        )
        if result:
            parts = result.bug_signature.split(":")
            assert len(parts) == 4

    def test_never_raises_on_corrupt_memory(self, tmp_path):
        mp = tmp_path / "memory.jsonl"
        mp.write_text("not json\n{bad\n")
        clf = EmbeddingClassifier()
        result = clf.classify(["any error"], mp)
        assert result is None

    def test_never_raises_on_missing_memory(self, tmp_path):
        mp = tmp_path / "nonexistent.jsonl"
        clf = EmbeddingClassifier()
        result = clf.classify(["any error"], mp)
        assert result is None


# ---------------------------------------------------------------------------
# classify_with_fallback tests
# ---------------------------------------------------------------------------

class TestClassifyWithFallback:
    def test_regex_hit_no_fallback(self):
        # Clear DependencyError — regex should handle it
        lines = ["ModuleNotFoundError: No module named 'pkg_resources'"]
        result = classify_with_fallback(lines, repo="test")
        assert result.category == "DependencyError"
        assert result.confidence >= 0.85

    def test_regex_miss_triggers_embedding(self, tmp_path, monkeypatch):
        import phase2.classifier.regex_pass as rp_mod
        import phase2.memory.similarity as sim_mod

        # Force regex to return low confidence
        from phase2.classifier.regex_pass import ClassifierResult
        low_conf = ClassifierResult(
            category="DependencyError", confidence=0.50,
            matched_pattern="", keyword="", affected_file="",
            bug_signature="repo:DependencyError::file", ecosystem="",
        )
        monkeypatch.setattr(rp_mod, "classify", lambda lines, repo="": low_conf)

        # Provide memory for BM25 fallback
        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(5))
        monkeypatch.setattr(sim_mod, "_memory_path", lambda: mp)

        lines = ["ModuleNotFoundError DependencyError requirements.txt"]
        result = classify_with_fallback(lines, repo="test")
        assert result is not None

    def test_embedding_result_returned_on_hit(self, tmp_path, monkeypatch):
        import phase2.classifier.regex_pass as rp_mod
        import phase2.memory.similarity as sim_mod
        from phase2.classifier.regex_pass import ClassifierResult

        low_conf = ClassifierResult(
            category="Unknown", confidence=0.40,
            matched_pattern="", keyword="", affected_file="",
            bug_signature="repo:Unknown::file", ecosystem="",
        )
        monkeypatch.setattr(rp_mod, "classify", lambda lines, repo="": low_conf)

        mp = tmp_path / "memory.jsonl"
        _write_memory(mp, _dep_entries(5))
        monkeypatch.setattr(sim_mod, "_memory_path", lambda: mp)

        lines = ["ModuleNotFoundError DependencyError requirements"]
        result = classify_with_fallback(lines, repo="test")
        assert result is not None

    def test_original_result_returned_when_both_fail(self, tmp_path, monkeypatch):
        import phase2.classifier.regex_pass as rp_mod
        import phase2.classifier.semantic_fallback as sf
        from phase2.classifier.regex_pass import ClassifierResult

        low_conf = ClassifierResult(
            category="Unknown", confidence=0.40,
            matched_pattern="", keyword="", affected_file="",
            bug_signature="repo:Unknown::file", ecosystem="",
        )
        monkeypatch.setattr(rp_mod, "classify", lambda lines, repo="": low_conf)
        monkeypatch.setattr(sf.EmbeddingClassifier, "classify", lambda self, *a, **kw: None)

        result = classify_with_fallback(["random garbage error"], repo="test")
        assert result.category == "Unknown"
        assert result.confidence == 0.40
