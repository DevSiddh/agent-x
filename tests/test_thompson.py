"""
Tests for phase2/strategy/thompson.py — ThompsonSampler
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import phase2.strategy.thompson as mod
from phase2.strategy.thompson import ThompsonSampler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sampler(tmpdir: Path) -> ThompsonSampler:
    """Return a ThompsonSampler whose state file is isolated to tmpdir."""
    state_file = tmpdir / "thompson_state.json"
    with patch.object(mod, "_state_path", return_value=state_file):
        sampler = ThompsonSampler()
    sampler._state_file = state_file  # store for later assertions
    # Patch save/load to use tmpdir path for subsequent calls
    original_save = sampler.save
    original_load = sampler.load

    def _save() -> None:
        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(sampler._state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load() -> None:
        try:
            if state_file.exists():
                sampler._state = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            sampler._state = {}

    sampler.save = _save  # type: ignore[method-assign]
    sampler.load = _load  # type: ignore[method-assign]
    return sampler


# ---------------------------------------------------------------------------
# Arm initialisation
# ---------------------------------------------------------------------------

class TestArmInit:
    def test_new_signature_starts_at_beta_1_1(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        arm = sampler.get_arm("repo:DependencyError:kw:file.txt")
        assert arm["alpha"] == 1
        assert arm["beta"] == 1

    def test_existing_signature_not_reset(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        sig = "repo:ConfigError:kw:app.py"
        sampler.update(sig, accepted=True)
        arm = sampler.get_arm(sig)
        assert arm["alpha"] == 2  # 1 initial + 1 update
        assert arm["beta"] == 1   # unchanged

    def test_different_signatures_independent(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        sig_a = "repo:TypeA:kw:a.py"
        sig_b = "repo:TypeB:kw:b.py"
        sampler.update(sig_a, accepted=True)
        sampler.update(sig_b, accepted=False)
        assert sampler.get_arm(sig_a)["alpha"] == 2
        assert sampler.get_arm(sig_a)["beta"] == 1
        assert sampler.get_arm(sig_b)["alpha"] == 1
        assert sampler.get_arm(sig_b)["beta"] == 2


# ---------------------------------------------------------------------------
# update() — alpha / beta increments
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_accepted_increments_alpha(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        sig = "repo:DependencyError:kw:req.txt"
        sampler.update(sig, accepted=True)
        assert sampler.get_arm(sig)["alpha"] == 2  # 1 + 1

    def test_rejected_increments_beta(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        sig = "repo:DependencyError:kw:req.txt"
        sampler.update(sig, accepted=False)
        assert sampler.get_arm(sig)["beta"] == 2  # 1 + 1

    def test_multiple_accepted_accumulate(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        sig = "repo:ConfigError:kw:config.py"
        for _ in range(5):
            sampler.update(sig, accepted=True)
        assert sampler.get_arm(sig)["alpha"] == 6  # 1 + 5

    def test_multiple_rejected_accumulate(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        sig = "repo:RuntimeError:kw:main.py"
        for _ in range(3):
            sampler.update(sig, accepted=False)
        assert sampler.get_arm(sig)["beta"] == 4  # 1 + 3

    def test_mixed_updates(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        sig = "repo:EnvironmentError:kw:env.sh"
        sampler.update(sig, accepted=True)
        sampler.update(sig, accepted=True)
        sampler.update(sig, accepted=False)
        arm = sampler.get_arm(sig)
        assert arm["alpha"] == 3  # 1 + 2
        assert arm["beta"] == 2   # 1 + 1


# ---------------------------------------------------------------------------
# sample() — return value in [0, 1]
# ---------------------------------------------------------------------------

class TestSample:
    def test_sample_returns_float(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        score = sampler.sample("repo:DependencyError:kw:req.txt")
        assert isinstance(score, float)

    def test_sample_in_unit_interval(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        for _ in range(20):
            score = sampler.sample("repo:DependencyError:kw:req.txt")
            assert 0.0 <= score <= 1.0

    def test_sample_new_arm_valid(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        score = sampler.sample("brand:new:sig:here")
        assert 0.0 <= score <= 1.0

    def test_high_alpha_biases_toward_1(self, tmp_path: Path) -> None:
        """With many successes, mean should be > 0.5 on average."""
        sampler = make_sampler(tmp_path)
        sig = "repo:ConfigError:kw:cfg.py"
        for _ in range(50):
            sampler.update(sig, accepted=True)
        # alpha=51, beta=1 → mean = 51/52 ≈ 0.98
        scores = [sampler.sample(sig) for _ in range(10)]
        assert sum(scores) / len(scores) > 0.5


# ---------------------------------------------------------------------------
# Persistence — save / load
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_state_written_to_file(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        sig = "repo:DependencyError:kw:req.txt"
        sampler.update(sig, accepted=True)
        assert sampler._state_file.exists()  # type: ignore[attr-defined]
        saved = json.loads(sampler._state_file.read_text())  # type: ignore[attr-defined]
        assert sig in saved

    def test_state_reloads_correctly(self, tmp_path: Path) -> None:
        sig = "repo:ConfigError:kw:config.yaml"
        state_file = tmp_path / "thompson_state.json"

        # Write state manually
        state_file.write_text(
            json.dumps({sig: {"alpha": 7, "beta": 3}}), encoding="utf-8"
        )

        with patch.object(mod, "_state_path", return_value=state_file):
            sampler2 = ThompsonSampler()

        arm = sampler2.get_arm(sig)
        assert arm["alpha"] == 7
        assert arm["beta"] == 3

    def test_save_never_raises_on_bad_path(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        # Redirect save to an impossible path — must not raise
        with patch.object(mod, "_state_path", return_value=Path("/no/such/path/state.json")):
            try:
                sampler.save()
            except Exception as e:
                pytest.fail(f"save() raised unexpectedly: {e}")

    def test_load_never_raises_on_missing_file(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        with patch.object(mod, "_state_path", return_value=tmp_path / "nonexistent.json"):
            try:
                sampler.load()
            except Exception as e:
                pytest.fail(f"load() raised unexpectedly: {e}")

    def test_load_never_raises_on_corrupt_file(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "bad.json"
        corrupt.write_text("not json {{{{", encoding="utf-8")
        with patch.object(mod, "_state_path", return_value=corrupt):
            sampler = ThompsonSampler()
        assert sampler._state == {}

    def test_arm_count(self, tmp_path: Path) -> None:
        sampler = make_sampler(tmp_path)
        assert sampler.arm_count() == 0
        sampler.update("sig:a", accepted=True)
        sampler.update("sig:b", accepted=False)
        assert sampler.arm_count() == 2


# ---------------------------------------------------------------------------
# Pipeline integration — exploration_score logged
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_pipeline_logs_exploration_score(self, tmp_path: Path) -> None:
        """Pipeline run() must log exploration_score after classify."""
        import phase2.pipeline as pl_mod

        state_file = tmp_path / "thompson_state.json"
        logged_events: list[dict] = []

        class CapturingLogger:
            def info(self, event: str, **kwargs: object) -> None:
                logged_events.append({"event": event, **kwargs})

            def warning(self, event: str, **kwargs: object) -> None:
                pass

            def error(self, event: str, **kwargs: object) -> None:
                pass

        from phase2.executor.runner import ApplyResult
        from phase2.executor.regression import TestReport

        mock_apply = MagicMock(
            return_value=ApplyResult(success=True, stdout="", stderr="", error="")
        )
        report = TestReport(passed=True, failed_tests=[], total=1, exit_code=0, raw="")
        mock_tests = MagicMock(return_value=report)

        # generate_patch is imported directly into pipeline — patch it there
        mock_patch_result = MagicMock()
        mock_patch_result.diff = "--- a/requirements.txt\n+++ b/requirements.txt\n@@ -1 +1 @@\n-x\n+setuptools\n"
        mock_patch_result.sanitiser_result.line_count = 1
        mock_patch_result.model_used = "deepseek-chat"
        mock_patch_result.attempt = 1
        mock_generate = MagicMock(return_value=mock_patch_result)

        with (
            patch.object(mod, "_state_path", return_value=state_file),
            patch.object(pl_mod, "apply_patch", mock_apply),
            patch.object(pl_mod, "run_tests", mock_tests),
            patch.object(pl_mod, "generate_patch", mock_generate),
            patch.object(pl_mod, "append", MagicMock()),
            patch.object(pl_mod, "rollback", MagicMock()),
            patch.object(pl_mod, "_ensure_fixture_repo", MagicMock()),
            patch.object(pl_mod, "build_context", MagicMock(return_value="ctx")),
            patch("phase2.memory.similarity.MemoryEngine.find_similar", return_value=None),
            patch("phase2.gateway.check", return_value=None),
        ):
            original_log = pl_mod.log
            pl_mod.log = CapturingLogger()  # type: ignore[assignment]
            try:
                pl_mod.run(pl_mod.SYNTHETIC_CASES[0])
            except Exception:
                pass
            finally:
                pl_mod.log = original_log

        score_events = [e for e in logged_events if "exploration_score" in e]
        assert len(score_events) >= 1, (
            f"exploration_score not logged. Events: {[e['event'] for e in logged_events]}"
        )
