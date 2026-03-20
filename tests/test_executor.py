"""
tests/test_executor.py
Step 5 — phase2/executor/runner.py + regression.py
Uses real git apply + real pytest on fixture repos (no mocks).
conftest.py guarantees fixtures are git repos before tests run.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.executor.regression import TestReport, check_regression, run_tests
from phase2.executor.runner import ApplyResult, apply_patch, rollback

REPO_ROOT = Path(__file__).resolve().parents[1]
JSONL_PATH = REPO_ROOT / "phase1" / "dataset" / "synthetic.jsonl"
FIXTURE_SYN001 = REPO_ROOT / "fixtures" / "syn_001"


def _load_patch(case_id: str) -> str:
    with open(JSONL_PATH) as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                if case["id"] == case_id:
                    return case["expected_patch"]
    raise ValueError(f"{case_id} not found")


@pytest.fixture(autouse=True)
def reset_syn001():
    """Reset syn_001 fixture to clean state before and after each test."""
    rollback(FIXTURE_SYN001)
    yield
    rollback(FIXTURE_SYN001)


# ── apply_patch ───────────────────────────────────────────────────────────────

class TestApplyPatch:

    def test_succeeds_with_valid_diff(self) -> None:
        patch = _load_patch("syn_001")
        result = apply_patch(patch, FIXTURE_SYN001)
        assert result.success is True
        assert result.error == ""

    def test_returns_apply_result_model(self) -> None:
        patch = _load_patch("syn_001")
        result = apply_patch(patch, FIXTURE_SYN001)
        assert isinstance(result, ApplyResult)

    def test_file_modified_after_apply(self) -> None:
        patch = _load_patch("syn_001")
        apply_patch(patch, FIXTURE_SYN001)
        content = (FIXTURE_SYN001 / "requirements.txt").read_text()
        assert "setuptools" in content

    def test_fails_gracefully_with_bad_diff(self) -> None:
        result = apply_patch("this is not a diff", FIXTURE_SYN001)
        assert result.success is False
        assert result.error != ""

    def test_fails_gracefully_with_empty_diff(self) -> None:
        result = apply_patch("", FIXTURE_SYN001)
        assert result.success is False

    def test_double_apply_fails(self) -> None:
        """Applying same patch twice should fail — file already patched."""
        patch = _load_patch("syn_001")
        apply_patch(patch, FIXTURE_SYN001)
        result = apply_patch(patch, FIXTURE_SYN001)
        assert result.success is False


# ── rollback ──────────────────────────────────────────────────────────────────

class TestRollback:

    def test_rollback_restores_file(self) -> None:
        original = (FIXTURE_SYN001 / "requirements.txt").read_text()
        patch = _load_patch("syn_001")
        apply_patch(patch, FIXTURE_SYN001)

        modified = (FIXTURE_SYN001 / "requirements.txt").read_text()
        assert modified != original

        rollback(FIXTURE_SYN001)
        restored = (FIXTURE_SYN001 / "requirements.txt").read_text()
        assert restored == original

    def test_rollback_idempotent_on_clean_repo(self) -> None:
        """Rollback on already-clean repo should not error."""
        rollback(FIXTURE_SYN001)  # no patch applied
        rollback(FIXTURE_SYN001)  # second rollback — should be fine


# ── run_tests ─────────────────────────────────────────────────────────────────

class TestRunTests:

    def test_returns_test_report_model(self) -> None:
        report = run_tests(FIXTURE_SYN001)
        assert isinstance(report, TestReport)

    def test_passed_on_clean_fixture(self) -> None:
        report = run_tests(FIXTURE_SYN001)
        assert report.passed is True

    def test_total_reflects_test_count(self) -> None:
        report = run_tests(FIXTURE_SYN001)
        assert report.total >= 1

    def test_no_failures_on_clean_fixture(self) -> None:
        report = run_tests(FIXTURE_SYN001)
        assert report.failed_tests == []

    def test_exit_code_zero_on_pass(self) -> None:
        report = run_tests(FIXTURE_SYN001)
        assert report.exit_code == 0


# ── check_regression ─────────────────────────────────────────────────────────

class TestCheckRegression:

    def _report(self, failed: list[str]) -> TestReport:
        return TestReport(
            passed=len(failed) == 0,
            failed_tests=failed,
            total=len(failed) + 1,
            exit_code=0 if not failed else 1,
            raw="",
        )

    def test_no_regression_when_same_failures(self) -> None:
        before = self._report(["tests/test_foo.py::test_a"])
        after  = self._report(["tests/test_foo.py::test_a"])
        assert check_regression(before, after) is False

    def test_no_regression_when_fewer_failures(self) -> None:
        before = self._report(["tests/test_foo.py::test_a", "tests/test_foo.py::test_b"])
        after  = self._report(["tests/test_foo.py::test_a"])
        assert check_regression(before, after) is False

    def test_regression_when_new_failures(self) -> None:
        before = self._report([])
        after  = self._report(["tests/test_foo.py::test_new"])
        assert check_regression(before, after) is True

    def test_regression_when_more_failures(self) -> None:
        before = self._report(["tests/test_foo.py::test_a"])
        after  = self._report(["tests/test_foo.py::test_a", "tests/test_foo.py::test_b"])
        assert check_regression(before, after) is True

    def test_no_regression_on_clean_before_and_after(self) -> None:
        before = self._report([])
        after  = self._report([])
        assert check_regression(before, after) is False
