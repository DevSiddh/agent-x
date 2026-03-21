"""
tests/test_hardening.py — Tests for C1 pipeline hardening.

Covers: run_tests_stable (flaky detection), Bandit gate, Radon gate,
structural escalation. All external tools are mocked.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.executor.regression import TestReport, run_tests_stable


# ── Helpers ────────────────────────────────────────────────────────────────────

def _passing_report() -> TestReport:
    return TestReport(passed=True, failed_tests=[], total=5, exit_code=0, raw="")


def _failing_report() -> TestReport:
    return TestReport(
        passed=False,
        failed_tests=["tests/test_x.py::test_fail"],
        total=5,
        exit_code=1,
        raw="",
    )


# ── run_tests_stable ───────────────────────────────────────────────────────────

class TestRunTestsStable:
    def test_all_pass_returns_passed_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "phase2.executor.regression.run_tests",
            lambda path: _passing_report(),
        )
        report = run_tests_stable(Path("/fake/fixture"), runs=3)
        assert report.passed is True
        assert report.note == ""

    def test_first_run_fails_returns_flaky(self, monkeypatch: pytest.MonkeyPatch) -> None:
        call_count = 0

        def _mock_run(path: Path) -> TestReport:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _failing_report()
            return _passing_report()

        monkeypatch.setattr("phase2.executor.regression.run_tests", _mock_run)
        report = run_tests_stable(Path("/fake/fixture"), runs=3)

        assert report.passed is False
        assert report.note == "flaky"
        assert call_count == 1  # stops on first failure

    def test_second_run_fails_returns_flaky(self, monkeypatch: pytest.MonkeyPatch) -> None:
        call_count = 0

        def _mock_run(path: Path) -> TestReport:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return _failing_report()
            return _passing_report()

        monkeypatch.setattr("phase2.executor.regression.run_tests", _mock_run)
        report = run_tests_stable(Path("/fake/fixture"), runs=3)

        assert report.passed is False
        assert report.note == "flaky"
        assert call_count == 2

    def test_runs_exactly_n_times_on_all_pass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        call_count = 0

        def _mock_run(path: Path) -> TestReport:
            nonlocal call_count
            call_count += 1
            return _passing_report()

        monkeypatch.setattr("phase2.executor.regression.run_tests", _mock_run)
        run_tests_stable(Path("/fake/fixture"), runs=3)
        assert call_count == 3


# ── Bandit gate ────────────────────────────────────────────────────────────────

class TestBanditGate:
    _DIFF_WITH_CODE = (
        "--- a/app.py\n+++ b/app.py\n"
        "+password = 'secret123'\n"
        "+import os\n"
    )
    _CLEAN_DIFF = (
        "--- a/requirements.txt\n+++ b/requirements.txt\n"
        "+setuptools\n"
    )

    def test_rejects_patch_when_bandit_returns_issue(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import phase2.pipeline as pipe

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Issue: B105 hardcoded password"
        mock_result.stderr = ""

        with patch("phase2.pipeline.subprocess") as mock_sp:
            mock_sp.run.return_value = mock_result
            result = pipe._run_bandit_check(
                self._DIFF_WITH_CODE, Path("/fake"), "app.py"
            )

        assert result != ""
        assert "B105" in result or "hardcoded" in result or "Issue" in result

    def test_passes_clean_patch_when_bandit_ok(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import phase2.pipeline as pipe

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("phase2.pipeline.subprocess") as mock_sp:
            mock_sp.run.return_value = mock_result
            result = pipe._run_bandit_check(
                self._CLEAN_DIFF, Path("/fake"), "requirements.txt"
            )

        assert result == ""

    def test_continues_gracefully_if_bandit_not_installed(self) -> None:
        import phase2.pipeline as pipe

        with patch("phase2.pipeline.subprocess") as mock_sp:
            mock_sp.run.side_effect = FileNotFoundError("bandit not found")
            result = pipe._run_bandit_check(
                self._DIFF_WITH_CODE, Path("/fake"), "app.py"
            )

        assert result == ""  # never raises, returns empty

    def test_returns_empty_for_diff_with_no_added_lines(self) -> None:
        import phase2.pipeline as pipe

        diff_no_adds = "--- a/f.py\n+++ b/f.py\n-removed_line\n"
        result = pipe._run_bandit_check(diff_no_adds, Path("/fake"), "f.py")
        assert result == ""


# ── Structural escalation ──────────────────────────────────────────────────────

class TestStructuralEscalation:
    def _mock_worker_result(self, passed: bool, attempt: int) -> MagicMock:
        r = MagicMock()
        r.sanitiser_result.passed = passed
        r.sanitiser_result.line_count = 20 if not passed else 5
        r.sanitiser_result.rejection_reason = "too many lines" if not passed else ""
        r.diff = "--- a/f.py\n+++ b/f.py\n+x\n"
        r.model_used = "deepseek-chat"
        r.attempt = attempt
        return r

    def test_structural_decision_after_3_line_limit_rejections(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import phase2.pipeline as pipe
        from phase2.memory.similarity import MemoryEngine

        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setattr("phase2.gateway.check", lambda *a, **kw: None)
        monkeypatch.setattr(
            "phase2.memory.similarity.MemoryEngine.find_similar",
            lambda self, *a, **kw: None,
        )
        monkeypatch.setattr(
            "phase2.pipeline.generate_patch",
            lambda *a, **kw: self._mock_worker_result(passed=False, attempt=3),
        )
        monkeypatch.setattr("phase2.pipeline.rollback", lambda path: None)
        monkeypatch.setattr("phase2.pipeline._ensure_fixture_repo", lambda path: None)
        monkeypatch.setattr("phase2.pipeline.reason", lambda *a: (_ for _ in ()).throw(
            __import__("agent_y.reasoner", fromlist=["ReasonerError"]).ReasonerError("skip")
        ))
        monkeypatch.setattr(
            "phase2.pipeline.run_tests",
            lambda path: TestReport(passed=True, failed_tests=[], total=5, exit_code=0, raw=""),
        )

        entry = pipe.run("syn_001")
        assert entry.decision == "structural"

    def test_no_structural_if_sanitiser_passed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import phase2.pipeline as pipe

        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
        monkeypatch.setattr(
            "phase2.memory.similarity.MemoryEngine.find_similar",
            lambda self, *a, **kw: None,
        )
        monkeypatch.setattr(
            "phase2.pipeline.generate_patch",
            lambda *a, **kw: self._mock_worker_result(passed=True, attempt=3),
        )
        monkeypatch.setattr("phase2.pipeline.rollback", lambda path: None)
        monkeypatch.setattr("phase2.pipeline._ensure_fixture_repo", lambda path: None)
        monkeypatch.setattr("phase2.pipeline.reason", lambda *a: (_ for _ in ()).throw(
            __import__("agent_y.reasoner", fromlist=["ReasonerError"]).ReasonerError("skip")
        ))
        monkeypatch.setattr(
            "phase2.pipeline.run_tests",
            lambda path: TestReport(passed=True, failed_tests=[], total=5, exit_code=0, raw=""),
        )
        monkeypatch.setattr(
            "phase2.pipeline.run_tests_stable",
            lambda path: TestReport(passed=True, failed_tests=[], total=5, exit_code=0, raw=""),
        )
        monkeypatch.setattr(
            "phase2.pipeline.apply_patch",
            lambda diff, path: type("R", (), {"success": True, "error": ""})(),
        )
        monkeypatch.setattr("phase2.pipeline.check_regression", lambda b, a: False)
        monkeypatch.setattr(
            "phase2.pipeline._run_bandit_check", lambda *a, **kw: ""
        )
        monkeypatch.setattr(
            "phase2.pipeline._run_radon_check", lambda *a, **kw: ""
        )

        entry = pipe.run("syn_001")
        assert entry.decision != "structural"
