"""
tests/test_embedding_classifier.py — Tests for EmbeddingClassifier + classify_with_fallback.

All tests mock _get_embedding_model() — never download the Jina model.
The fake encoder produces deterministic vectors per text content:
  - "DependencyError" / "ModuleNotFoundError" in text → [1, 0, 0]
  - "ConfigError" / "KeyError" in text               → [0, 1, 0]
  - anything else                                     → [0, 0, 1]  (orthogonal)

Centroid math (TF-IDF mocked, Jina=fake):
  DependencyError centroid = [1, 0, 0] (unit), ConfigError = [0, 1, 0]
  Query matching category → sim=1.0, S_next=0.0
  → confidence = min(0.87, 1.0 + 0.5×1.0) = 0.87

  Query orthogonal to all centroids → sim=0 for all
  → confidence = 0.0 < _CONFIDENCE_FLOOR (0.55) → returns None
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase2.memory.similarity as sim_mod
import phase2.classifier.semantic_fallback as sf_mod
from phase2.classifier.semantic_fallback import (
    EmbeddingClassifier,
    _CONFIDENCE_CAP,
    _CONFIDENCE_FLOOR,
    _MIN_ENTRIES_PER_CATEGORY,
)
from phase2.classifier.regex_pass import classify_with_fallback


# ── Fake encoder ─────────────────────────────────────────────────────────────

class _FakeSentenceTransformer:
    """
    Deterministic fake encoder. Maps text content to 3-d unit vectors:
      DependencyError / ModuleNotFoundError → [1, 0, 0]
      ConfigError / KeyError                → [0, 1, 0]
      anything else                         → [0, 0, 1]
    normalize_embeddings=True is honoured (vectors are already unit-length).
    """

    def encode(
        self,
        texts: list[str],
        normalize_embeddings: bool = False,
    ) -> np.ndarray:
        result: list[list[float]] = []
        for text in texts:
            if any(k in text for k in ("DependencyError", "ModuleNotFoundError")):
                result.append([1.0, 0.0, 0.0])
            elif any(k in text for k in ("ConfigError", "KeyError")):
                result.append([0.0, 1.0, 0.0])
            else:
                result.append([0.0, 0.0, 1.0])
        return np.array(result, dtype=float)


def _fake_model() -> _FakeSentenceTransformer:
    return _FakeSentenceTransformer()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_memory(path: Path, entries: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _accepted_entry(
    category: str = "DependencyError",
    sig: str = "org/repo:DependencyError:pkg_resources:requirements.txt",
    run_id: str = "abc123",
) -> dict:
    return {
        "run_id": run_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "source": "pipeline",
        "repo": "org/repo",
        "failure_category": category,
        "bug_signature": sig,
        "confidence_score": 0.99,
        "mode": "repair",
        "patch_applied": "+fix\n",
        "lines_changed": 1,
        "model_used": "deepseek-chat",
        "sandbox_result": "pass",
        "regression_introduced": False,
        "retries_used": 0,
        "mttr_seconds": 5.0,
        "decision": "accepted",
        "success_count": 1,
        "fail_count": 0,
        "error": "",
        "test_summary": "5 passed, 0 failed",
    }


def _dep_entries(n: int = 6) -> list[dict]:
    return [
        _accepted_entry(
            category="DependencyError",
            sig=f"org/repo:DependencyError:pkg_resources:requirements.txt",
            run_id=f"dep-{i:03d}",
        )
        for i in range(n)
    ]


def _cfg_entries(n: int = 6) -> list[dict]:
    return [
        _accepted_entry(
            category="ConfigError",
            sig=f"org/repo:ConfigError:no_such_table:app/database.py",
            run_id=f"cfg-{i:03d}",
        )
        for i in range(n)
    ]


@pytest.fixture(autouse=True)
def patch_sim_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect memory path in similarity module so EmbeddingClassifier reads tmp_path."""
    mem = tmp_path / "memory.jsonl"
    monkeypatch.setattr(sim_mod, "_memory_path", lambda: mem)


# ── TestEmbeddingClassifier ───────────────────────────────────────────────────

class TestEmbeddingClassifier:

    def test_returns_none_when_model_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Jina model unavailable → classify returns None immediately
        monkeypatch.setattr(sim_mod, "_get_embedding_model", lambda: None)
        engine = EmbeddingClassifier()
        result = engine.classify(
            ["ModuleNotFoundError: No module named 'pkg_resources'"], "test/repo"
        )
        assert result is None

    def test_returns_none_when_no_centroids_built(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Fake model available but memory.jsonl is empty → no centroids → None
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        engine = EmbeddingClassifier()
        result = engine.classify(
            ["ModuleNotFoundError: No module named 'pkg_resources'"], "test/repo"
        )
        assert result is None

    def test_returns_none_below_confidence_floor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Write enough DependencyError + ConfigError entries to build centroids.
        # Query with text orthogonal to both centroids → sim=0 → confidence=0 → None.
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(
            sim_mod._memory_path(),
            _dep_entries(6) + _cfg_entries(6),
        )
        engine = EmbeddingClassifier()
        # Text doesn't contain any category keyword → [0,0,1] → sim=0 with all centroids
        result = engine.classify(["unknown runtime crash xyzzy"], "test/repo")
        assert result is None

    def test_classifies_when_clear_winner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # DependencyError centroid [1,0,0]; query matches → sim=1.0
        # confidence = min(0.87, 1.0 + 0.5 × (1.0 - 0.0)) = 0.87
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(
            sim_mod._memory_path(),
            _dep_entries(6) + _cfg_entries(6),
        )
        engine = EmbeddingClassifier()
        result = engine.classify(
            ["ModuleNotFoundError: No module named 'some_new_package'"], "test/repo"
        )
        assert result is not None
        assert result.confidence == pytest.approx(_CONFIDENCE_CAP, abs=1e-6)
        assert result.matched_pattern == "semantic_centroid"

    def test_confidence_capped_at_087(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Perfect match → raw formula would be > 0.87 → must be capped at 0.87
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(sim_mod._memory_path(), _dep_entries(6))
        engine = EmbeddingClassifier()
        result = engine.classify(
            ["ModuleNotFoundError: No module named 'anything'"], "test/repo"
        )
        assert result is not None
        assert result.confidence <= _CONFIDENCE_CAP

    def test_skips_category_below_min_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Only 3 DependencyError entries (< _MIN_ENTRIES_PER_CATEGORY=5) → skipped
        # 6 ConfigError entries → included
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(
            sim_mod._memory_path(),
            _dep_entries(3) + _cfg_entries(6),
        )
        engine = EmbeddingClassifier()
        centroids = engine.build_centroids(sim_mod._memory_path())
        assert "DependencyError" not in centroids
        assert "ConfigError" in centroids

    def test_returns_correct_category(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # DependencyError + ConfigError centroids built.
        # Query with DependencyError keywords → classified as DependencyError.
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(
            sim_mod._memory_path(),
            _dep_entries(6) + _cfg_entries(6),
        )
        engine = EmbeddingClassifier()
        result = engine.classify(
            ["ModuleNotFoundError: No module named 'uv_package'"], "test/repo"
        )
        assert result is not None
        assert result.category == "DependencyError"

    def test_bug_signature_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # bug_signature must be "{repo}:{category}:semantic:unknown"
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(sim_mod._memory_path(), _dep_entries(6))
        engine = EmbeddingClassifier()
        result = engine.classify(
            ["ModuleNotFoundError: No module named 'pkg'"], "myorg/myrepo"
        )
        assert result is not None
        assert result.bug_signature == "myorg/myrepo:DependencyError:semantic:unknown"

    def test_matched_pattern_is_semantic_centroid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(sim_mod._memory_path(), _dep_entries(6))
        engine = EmbeddingClassifier()
        result = engine.classify(
            ["ModuleNotFoundError: No module named 'pkg'"], "test/repo"
        )
        assert result is not None
        assert result.matched_pattern == "semantic_centroid"


# ── TestClassifyWithFallback ───────────────────────────────────────────────────

class TestClassifyWithFallback:

    def test_regex_pass_skips_embedding(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regex confidence >= 0.85 → EmbeddingClassifier never instantiated
        instantiated: list[int] = []

        original_init = EmbeddingClassifier.__init__

        def _tracking_init(self: EmbeddingClassifier) -> None:
            instantiated.append(1)
            original_init(self)

        monkeypatch.setattr(
            sf_mod.EmbeddingClassifier, "__init__", _tracking_init
        )

        result = classify_with_fallback(
            ["ModuleNotFoundError: No module named 'pkg_resources'"],
            repo="test/repo",
        )
        assert result.confidence >= 0.85
        assert len(instantiated) == 0  # EmbeddingClassifier never instantiated

    def test_regex_miss_triggers_embedding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Error with no regex match → confidence low → embedding triggered
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(sim_mod._memory_path(), _dep_entries(6))

        classify_calls: list[int] = []
        original_classify = EmbeddingClassifier.classify

        def _tracking_classify(self: EmbeddingClassifier, *args: object, **kwargs: object) -> object:
            classify_calls.append(1)
            return original_classify(self, *args, **kwargs)

        monkeypatch.setattr(EmbeddingClassifier, "classify", _tracking_classify)

        # "build isolation error" → EnvironmentError pattern but low confidence
        # Use text that gives regex very low score → embedding triggered
        result = classify_with_fallback(
            ["some unknown framework error: xyzzy failed"],
            repo="test/repo",
        )
        # Embedding was at least attempted (may return None if no centroid match)
        assert len(classify_calls) >= 1

    def test_embedding_result_returned_on_hit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regex misses → embedding hits → return embedding result
        monkeypatch.setattr(sim_mod, "_get_embedding_model", _fake_model)
        _write_memory(sim_mod._memory_path(), _dep_entries(6))

        # Patch EmbeddingClassifier.classify to return a known result
        from phase2.classifier.regex_pass import ClassifierResult
        fake_result = ClassifierResult(
            category="DependencyError",
            confidence=0.87,
            matched_pattern="semantic_centroid",
            keyword="pkg",
            affected_file="",
            bug_signature="test/repo:DependencyError:semantic:unknown",
        )
        monkeypatch.setattr(
            EmbeddingClassifier, "classify", lambda self, *a, **kw: fake_result
        )

        result = classify_with_fallback(
            ["totally unknown error xyzzy"],
            repo="test/repo",
        )
        assert result.matched_pattern == "semantic_centroid"
        assert result.confidence == pytest.approx(0.87)

    def test_original_result_returned_when_both_fail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regex miss + embedding returns None → original low-confidence result returned
        monkeypatch.setattr(sim_mod, "_get_embedding_model", lambda: None)

        result = classify_with_fallback(
            ["totally unknown xyzzy error"],
            repo="test/repo",
        )
        # Must return a ClassifierResult (not None)
        assert result is not None
        # Embedding was not available → original regex result (low confidence)
        assert result.matched_pattern != "semantic_centroid"
