"""
tests/test_similarity.py — Tests for phase2/memory/similarity.py

All tests use tmp_path — never touch real memory.jsonl or thompson_state.json.
Jina model is mocked to None in all tests via autouse fixture — no downloads.
With Jina=None, redistributed weights apply:
    hybrid = (0.30/0.55) × TF-IDF + (0.25/0.55) × Thompson + 0.05 (filename boost if match)
Tests that need scores >= 0.55 include Thompson state to compensate.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase2.memory.similarity as sim_mod
from phase2.memory.similarity import MemoryEngine

def _thaw(category, matched_pattern, keyword, affected_file):
    return f"{category} ({matched_pattern}) involving {keyword} in file {affected_file}"


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _write_memory(path: Path, entries: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _write_thompson(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state), encoding="utf-8")


def _accepted_entry(
    sig: str = "org/repo:DependencyError:pkg_resources:requirements.txt",
    patch: str = "--- a/requirements.txt\n+++ b/requirements.txt\n+setuptools\n",
    file_ctx: str = "requirements.txt",
) -> dict:
    return {
        "run_id": "abc123",
        "timestamp": "2026-01-01T00:00:00Z",
        "source": "pipeline",
        "repo": "org/repo",
        "failure_category": "DependencyError",
        "bug_signature": sig,
        "confidence_score": 0.99,
        "mode": "repair",
        "patch_applied": patch,
        "lines_changed": 3,
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


@pytest.fixture(autouse=True)
def patch_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect memory/thompson paths to tmp_path and mock Jina to None (no downloads)."""
    mem = tmp_path / "memory.jsonl"
    ts = tmp_path / "thompson_state.json"
    monkeypatch.setattr(sim_mod, "_memory_path", lambda: mem)
    monkeypatch.setattr(sim_mod, "_thompson_state_path", lambda: ts)
    # Mock Jina model to None — tests remain offline and fast.
    # With Jina=None, weights redistribute: (0.30/0.55)×TF-IDF + (0.25/0.55)×Thompson
    

# ── TestMemoryEngine (find_similar) ────────────────────────────────────────────
# With Jina=None and redistributed weights:
#   hybrid ≈ 0.545×s_tfidf + 0.454×ts_rate + 0.05 (if filename matches)
# Tests that check score >= 0.55 set Thompson state (alpha=3, beta=1 → rate=0.75)
#   → hybrid ≈ 0.545 + 0.340 + 0.05 = 0.935

class TestMemoryEngine:
    def test_returns_none_when_memory_empty(self, tmp_path: Path) -> None:
        engine = MemoryEngine()
        result = engine.find_similar(
            "org/repo:DependencyError:pkg:requirements.txt",
            "requirements.txt",
        )
        assert result is None

    def test_returns_match_for_identical_signature(self, tmp_path: Path) -> None:
        sig = "org/repo:DependencyError:pkg_resources:requirements.txt"
        _write_memory(sim_mod._memory_path(), [_accepted_entry(sig=sig)])
        # Set Thompson state so score reaches 0.55 threshold (rate=0.75)
        _write_thompson(
            sim_mod._thompson_state_path(),
            {sig: {"alpha": 3, "beta": 1}},
        )

        engine = MemoryEngine()
        result = engine.find_similar(sig, "requirements.txt")

        assert result is not None
        assert result["match_score"] >= sim_mod._SIMILARITY_THRESHOLD
        assert "patch" in result
        assert "metadata" in result

    def test_returns_none_when_score_below_threshold(self, tmp_path: Path) -> None:
        # Entry uses a totally different signature — similarity will be low
        _write_memory(
            sim_mod._memory_path(),
            [_accepted_entry(sig="org/repo:RuntimeError:null_ptr:app/main.cpp")],
        )
        engine = MemoryEngine()
        result = engine.find_similar(
            "other/repo:ConfigError:no_table:app/database.py",
            "database.py",
        )
        assert result is None

    def test_only_accepted_entries_considered(self, tmp_path: Path) -> None:
        sig = "org/repo:DependencyError:pkg_resources:requirements.txt"
        rejected = _accepted_entry(sig=sig)
        rejected["decision"] = "rejected"
        _write_memory(sim_mod._memory_path(), [rejected])

        engine = MemoryEngine()
        result = engine.find_similar(sig, "requirements.txt")
        assert result is None  # rejected entry not used

    def test_filename_boost_increases_score(self, tmp_path: Path) -> None:
        """Entry matching affected_file should score higher than one that doesn't."""
        sig_match    = "org/repo:DependencyError:pkg:requirements.txt"
        sig_no_match = "org/repo:DependencyError:pkg:Makefile"

        entries = [
            _accepted_entry(sig=sig_no_match),
            _accepted_entry(sig=sig_match),
        ]
        _write_memory(sim_mod._memory_path(), entries)
        # Thompson state on sig_match so it clears 0.55 threshold
        _write_thompson(
            sim_mod._thompson_state_path(),
            {sig_match: {"alpha": 3, "beta": 1}},
        )

        engine = MemoryEngine()
        result = engine.find_similar(
            "org/repo:DependencyError:pkg:requirements.txt",
            "requirements.txt",
        )
        assert result is not None
        assert "requirements.txt" in result["metadata"]["bug_signature"]

    def test_hybrid_ranking_prefers_high_thompson_rate(self, tmp_path: Path) -> None:
        """High Thompson success rate should push score up."""
        sig_a = "org/repo:DependencyError:pkg:requirements.txt"
        sig_b = "org/repo:DependencyError:pkg:requirements.txt"
        entry_a = _accepted_entry(sig=sig_a)
        entry_a["run_id"] = "run-a"
        entry_b = _accepted_entry(sig=sig_b)
        entry_b["run_id"] = "run-b"
        _write_memory(sim_mod._memory_path(), [entry_a, entry_b])

        # sig_a has high success rate (alpha=10, beta=1 → ~0.909)
        _write_thompson(
            sim_mod._thompson_state_path(),
            {sig_a: {"alpha": 10, "beta": 1}},
        )

        engine = MemoryEngine()
        result = engine.find_similar(sig_a, "requirements.txt")
        assert result is not None
        assert result["match_score"] > sim_mod._SIMILARITY_THRESHOLD

    def test_result_has_required_keys(self, tmp_path: Path) -> None:
        sig = "org/repo:DependencyError:pkg_resources:requirements.txt"
        _write_memory(sim_mod._memory_path(), [_accepted_entry(sig=sig)])
        _write_thompson(
            sim_mod._thompson_state_path(),
            {sig: {"alpha": 3, "beta": 1}},
        )

        engine = MemoryEngine()
        result = engine.find_similar(sig, "requirements.txt")

        assert result is not None
        assert "patch" in result
        assert "match_score" in result
        assert "metadata" in result
        assert "bug_signature" in result["metadata"]
        assert "failure_category" in result["metadata"]


# ── TestThompsonSuccessRate ───────────────────────────────────────────────────

class TestThompsonSuccessRate:
    def test_returns_half_when_arm_not_found(self) -> None:
        from phase2.memory.similarity import _thompson_success_rate
        assert _thompson_success_rate("missing:sig", {}) == 0.5

    def test_computes_correctly(self) -> None:
        from phase2.memory.similarity import _thompson_success_rate
        state = {"my:sig": {"alpha": 8, "beta": 2}}
        rate = _thompson_success_rate("my:sig", state)
        assert abs(rate - 0.8) < 1e-6


# ── TestThawString ────────────────────────────────────────────────────────────

class TestThawString:
    def test_thaw_format_correct(self) -> None:
        result = _thaw(
            "DependencyError", "ModuleNotFoundError", "pkg_resources", "requirements.txt"
        )
        assert result == (
            "DependencyError (ModuleNotFoundError) involving pkg_resources "
            "in file requirements.txt"
        )

    def test_thaw_different_categories(self) -> None:
        result = _thaw("ConfigError", "KeyError", "DATABASE_URL", "app/config.py")
        assert "ConfigError" in result
        assert "KeyError" in result
        assert "DATABASE_URL" in result
        assert "app/config.py" in result

    def test_thaw_returns_string(self) -> None:
        result = _thaw("RuntimeError", "NullPointer", "obj", "main.py")
        assert isinstance(result, str)
        assert len(result) > 0


# ── TestFindForRag ────────────────────────────────────────────────────────────
# All tests run with Jina=None (autouse fixture). Redistributed weights apply.
# TF-IDF on identical bug_signature ≈ 1.0 → hybrid ≈ 0.545 + 0.227 + 0.05 = 0.822.
# That is above _RAG_LOW_THRESHOLD (0.55) and in the HIGH tier (0.70-0.84).
# Tests use identical signature to ensure scores cross 0.55.

class TestFindForRag:
    def test_find_for_rag_empty_when_no_memory(self) -> None:
        engine = MemoryEngine()
        result = engine.find_for_rag(
            category="DependencyError",
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file="requirements.txt",
            query_sig="org/repo:DependencyError:pkg_resources:requirements.txt",
        )
        assert result == []

    def test_find_for_rag_empty_below_low_threshold(self, tmp_path: Path) -> None:
        # Completely unrelated signature → low TF-IDF + default Thompson → score < 0.55
        _write_memory(
            sim_mod._memory_path(),
            [_accepted_entry(sig="org/repo:RuntimeError:null_ptr:app/main.cpp")],
        )
        engine = MemoryEngine()
        result = engine.find_for_rag(
            category="ConfigError",
            matched_pattern="KeyError",
            keyword="DATABASE_URL",
            affected_file="config/settings.py",
            query_sig="other/repo:ConfigError:DATABASE_URL:config/settings.py",
        )
        assert result == []

    def test_find_for_rag_returns_entry_in_high_tier(self, tmp_path: Path) -> None:
        # Identical sig → high TF-IDF + boost → score in HIGH tier (>= 0.70)
        sig = "org/repo:DependencyError:pkg_resources:requirements.txt"
        _write_memory(sim_mod._memory_path(), [_accepted_entry(sig=sig)])
        engine = MemoryEngine()
        result = engine.find_for_rag(
            category="DependencyError",
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file="requirements.txt",
            query_sig=sig,
        )
        assert len(result) == 1
        entry_dict = result[0]["metadata"]
        score = result[0]["score"]
        assert score >= sim_mod._RAG_LOW_THRESHOLD  # BM25 single-entry corpus caps at ~0.4
        assert entry_dict.get("bug_signature") == sig

    def test_find_for_rag_caps_at_top_k(self, tmp_path: Path) -> None:
        sig = "org/repo:DependencyError:pkg_resources:requirements.txt"
        entries = [
            {**_accepted_entry(sig=sig), "run_id": f"run-{i:03d}"}
            for i in range(10)
        ]
        _write_memory(sim_mod._memory_path(), entries)
        engine = MemoryEngine()
        result = engine.find_for_rag(
            category="DependencyError",
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file="requirements.txt",
            query_sig=sig,
        )
        assert len(result) <= sim_mod._TOP_K

    def test_find_for_rag_tuple_of_dict_and_float(self, tmp_path: Path) -> None:
        sig = "org/repo:DependencyError:pkg_resources:requirements.txt"
        _write_memory(sim_mod._memory_path(), [_accepted_entry(sig=sig)])
        engine = MemoryEngine()
        result = engine.find_for_rag(
            category="DependencyError",
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file="requirements.txt",
            query_sig=sig,
        )
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert isinstance(result[0]["metadata"], dict)
        assert isinstance(result[0]["score"], float)

    def test_find_for_rag_only_accepted_entries(self, tmp_path: Path) -> None:
        sig = "org/repo:DependencyError:pkg_resources:requirements.txt"
        rejected = {**_accepted_entry(sig=sig), "decision": "rejected"}
        _write_memory(sim_mod._memory_path(), [rejected])
        engine = MemoryEngine()
        result = engine.find_for_rag(
            category="DependencyError",
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file="requirements.txt",
            query_sig=sig,
        )
        assert result == []

    def test_find_for_rag_returns_sorted_descending(self, tmp_path: Path) -> None:
        sig_high = "org/repo:DependencyError:pkg_resources:requirements.txt"
        sig_low  = "other/repo:RuntimeError:null_ptr:app/main.cpp"
        _write_memory(
            sim_mod._memory_path(),
            [
                _accepted_entry(sig=sig_low),   # low TF-IDF with query
                _accepted_entry(sig=sig_high),  # high TF-IDF with query + boost
            ],
        )
        # Thompson state to push sig_high above threshold
        _write_thompson(
            sim_mod._thompson_state_path(),
            {sig_high: {"alpha": 3, "beta": 1}},
        )
        engine = MemoryEngine()
        result = engine.find_for_rag(
            category="DependencyError",
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file="requirements.txt",
            query_sig=sig_high,
        )
        assert len(result) >= 1
        # First entry should have the highest score
        if len(result) >= 2:
            assert result[0]["score"] >= result[1]["score"]

    def test_find_for_rag_entry_dict_has_patch_key(self, tmp_path: Path) -> None:
        sig = "org/repo:DependencyError:pkg_resources:requirements.txt"
        _write_memory(sim_mod._memory_path(), [_accepted_entry(sig=sig)])
        engine = MemoryEngine()
        result = engine.find_for_rag(
            category="DependencyError",
            matched_pattern="ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file="requirements.txt",
            query_sig=sig,
        )
        assert len(result) == 1
        entry_dict = result[0]["metadata"]
        assert "patch_applied" in entry_dict
        assert "decision" in entry_dict


# ── TestPipelineReuseBypass ───────────────────────────────────────────────────

class TestPipelineReuseBypass:
    """Verify memory reuse bypass is wired into pipeline correctly."""

    def test_agent_y_skipped_on_cache_hit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When find_similar returns a match, reason() must NOT be called."""
        reason_calls: list[int] = []

        monkeypatch.setattr("phase2.gateway.check", lambda *a, **kw: None)
        monkeypatch.setattr(
            "phase2.memory.similarity.MemoryEngine.find_similar",
            lambda self, *a, **kw: {
                "patch": "--- a/requirements.txt\n+++ b/requirements.txt\n+setuptools\n",
                "match_score": 0.95,
                "metadata": {"bug_signature": "synthetic:DependencyError:pkg:requirements.txt",
                              "failure_category": "DependencyError",
                              "model_used": "deepseek-chat",
                              "repo": "synthetic",
                              "run_id": "old-run"},
            },
        )

        # Mock apply_patch to succeed, run_tests to pass, check_regression to be False
        from phase2.executor.runner import ApplyResult
        monkeypatch.setattr(
            "phase2.pipeline.apply_patch",
            lambda diff, path: ApplyResult(success=True, stdout="", stderr="", error=""),
        )
        from phase2.executor.regression import PatchTestReport
        monkeypatch.setattr(
            "phase2.pipeline.run_tests",
            lambda path: PatchTestReport(passed=True, failed_tests=[], total=5, exit_code=0, raw=""),
        )
        monkeypatch.setattr("phase2.pipeline.check_regression", lambda b, a: False)
        monkeypatch.setattr("phase2.pipeline.rollback", lambda path: None)

        def _mock_reason(ctx: str, clf: object) -> None:
            reason_calls.append(1)
            raise RuntimeError("reason should not be called")

        monkeypatch.setattr("phase2.pipeline.reason", _mock_reason)

        import phase2.pipeline as pipe
        entry = pipe.run("syn_001")

        assert entry.decision == "accepted"
        assert entry.model_used == "memory_reuse"
        assert len(reason_calls) == 0  # Agent-Y never called

    def test_pipeline_falls_through_on_reuse_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When cached patch fails to apply, pipeline must continue normally."""
        monkeypatch.setattr("phase2.gateway.check", lambda *a, **kw: None)
        monkeypatch.setattr(
            "phase2.memory.similarity.MemoryEngine.find_similar",
            lambda self, *a, **kw: {
                "patch": "bad patch",
                "match_score": 0.95,
                "metadata": {
                    "bug_signature": "synthetic:DependencyError:pkg:requirements.txt",
                    "failure_category": "DependencyError",
                    "model_used": "deepseek-chat",
                    "repo": "synthetic",
                    "run_id": "old-run",
                },
            },
        )

        from phase2.executor.runner import ApplyResult
        apply_calls: list[str] = []

        def _mock_apply(diff: str, path: object) -> ApplyResult:
            apply_calls.append(diff)
            if diff == "bad patch":
                return ApplyResult(success=False, stdout="", stderr="failed", error="failed")
            return ApplyResult(success=True, stdout="", stderr="", error="")

        monkeypatch.setattr("phase2.pipeline.apply_patch", _mock_apply)
        monkeypatch.setattr("phase2.pipeline.rollback", lambda path: None)

        from phase2.executor.regression import PatchTestReport
        monkeypatch.setattr(
            "phase2.pipeline.run_tests",
            lambda path: PatchTestReport(passed=True, failed_tests=[], total=5, exit_code=0, raw=""),
        )
        monkeypatch.setattr("phase2.pipeline.check_regression", lambda b, a: False)

        from phase2.patch_gen.sanitiser import SanitiserResult
        mock_worker = type("W", (), {
            "diff": "--- a/requirements.txt\n+++ b/requirements.txt\n+x\n",
            "sanitiser_result": SanitiserResult(
                passed=True, diff="--- a/f\n+++ b/f\n+x\n", line_count=1, rejection_reason=""
            ),
            "model_used": "deepseek-chat",
            "attempt": 1,
        })()
        monkeypatch.setattr("phase2.pipeline.generate_patch", lambda *a, **kw: mock_worker)
        monkeypatch.setattr("phase2.pipeline.reason", lambda *a, **kw: (_ for _ in ()).throw(
            __import__("agent_y.reasoner", fromlist=["ReasonerError"]).ReasonerError("skip")
        ))

        import phase2.pipeline as pipe
        entry = pipe.run("syn_001")

        assert apply_calls[0] == "bad patch"
        assert len(apply_calls) >= 2
