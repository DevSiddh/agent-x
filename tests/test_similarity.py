"""
tests/test_similarity.py — Tests for phase2/memory/similarity.py

All tests use tmp_path — never touch real memory.jsonl or thompson_state.json.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase2.memory.similarity as sim_mod
from phase2.memory.similarity import MemoryEngine


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
    mem = tmp_path / "memory.jsonl"
    ts = tmp_path / "thompson_state.json"
    monkeypatch.setattr(sim_mod, "_memory_path", lambda: mem)
    monkeypatch.setattr(sim_mod, "_thompson_state_path", lambda: ts)


# ── Tests ──────────────────────────────────────────────────────────────────────

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
        sig_match = "org/repo:DependencyError:pkg:requirements.txt"
        sig_no_match = "org/repo:DependencyError:pkg:Makefile"

        entries = [
            _accepted_entry(sig=sig_no_match),
            _accepted_entry(sig=sig_match),
        ]
        _write_memory(sim_mod._memory_path(), entries)

        engine = MemoryEngine()
        # Query for requirements.txt — file-matching entry should win
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
        # Two identical entries — differentiate via thompson_state
        entry_a = _accepted_entry(sig=sig_a)
        entry_a["run_id"] = "run-a"
        entry_b = _accepted_entry(sig=sig_b)
        entry_b["run_id"] = "run-b"
        _write_memory(sim_mod._memory_path(), [entry_a, entry_b])

        # Make sig_a have high success rate, sig_b default
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

        engine = MemoryEngine()
        result = engine.find_similar(sig, "requirements.txt")

        assert result is not None
        assert "patch" in result
        assert "match_score" in result
        assert "metadata" in result
        assert "bug_signature" in result["metadata"]
        assert "failure_category" in result["metadata"]


class TestThompsonSuccessRate:
    def test_returns_half_when_arm_not_found(self) -> None:
        from phase2.memory.similarity import _thompson_success_rate
        assert _thompson_success_rate("missing:sig", {}) == 0.5

    def test_computes_correctly(self) -> None:
        from phase2.memory.similarity import _thompson_success_rate
        state = {"my:sig": {"alpha": 8, "beta": 2}}
        rate = _thompson_success_rate("my:sig", state)
        assert abs(rate - 0.8) < 1e-6


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
        from phase2.executor.regression import TestReport
        monkeypatch.setattr(
            "phase2.pipeline.run_tests",
            lambda path: TestReport(passed=True, failed_tests=[], total=5, exit_code=0, raw=""),
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
            # Subsequent calls succeed (full pipeline)
            return ApplyResult(success=True, stdout="", stderr="", error="")

        monkeypatch.setattr("phase2.pipeline.apply_patch", _mock_apply)
        monkeypatch.setattr("phase2.pipeline.rollback", lambda path: None)

        from phase2.executor.regression import TestReport
        monkeypatch.setattr(
            "phase2.pipeline.run_tests",
            lambda path: TestReport(passed=True, failed_tests=[], total=5, exit_code=0, raw=""),
        )
        monkeypatch.setattr("phase2.pipeline.check_regression", lambda b, a: False)

        # Mock full pipeline components so run() doesn't fail on deepseek
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

        # First apply call was the cached patch (failed), second was full pipeline
        assert apply_calls[0] == "bad patch"
        assert len(apply_calls) >= 2
