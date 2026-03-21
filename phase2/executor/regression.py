"""
phase2/executor/regression.py
Runs pytest on a fixture repo and compares before/after failure counts. (P7)
Uses pytest-json-report for structured output.
"""

import json
import subprocess
import sys
from pathlib import Path

import structlog
from pydantic import BaseModel

log = structlog.get_logger()


class TestReport(BaseModel):
    passed: bool
    failed_tests: list[str]
    total: int
    exit_code: int
    raw: str
    note: str = ""   # "flaky" when run_tests_stable detects intermittent failures (C1)


def run_tests(fixture_path: Path) -> TestReport:
    """
    Run pytest on a fixture repo and return structured results.

    Args:
        fixture_path: Path to the fixture git repo.

    Returns:
        TestReport with passed, failed_tests, total, exit_code, raw output.
    """
    fixture_path = Path(fixture_path).resolve()
    report_file = fixture_path / "report.json"

    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/",
            "--tb=short",
            "--json-report",
            f"--json-report-file={report_file}",
            "-q",
        ],
        cwd=fixture_path,
        capture_output=True,
        text=True,
    )

    failed_tests: list[str] = []
    total = 0

    if report_file.exists():
        try:
            report_data = json.loads(report_file.read_text())
            total = report_data.get("summary", {}).get("total", 0)
            for test in report_data.get("tests", []):
                if test.get("outcome") == "failed":
                    failed_tests.append(test.get("nodeid", "unknown"))
        except (json.JSONDecodeError, KeyError):
            pass
        finally:
            report_file.unlink(missing_ok=True)

    passed = result.returncode == 0

    log.info(
        "regression.test_run",
        fixture=str(fixture_path),
        passed=passed,
        failed=len(failed_tests),
        total=total,
    )

    return TestReport(
        passed=passed,
        failed_tests=failed_tests,
        total=total,
        exit_code=result.returncode,
        raw=result.stdout + result.stderr,
    )


def run_tests_stable(fixture_path: Path, runs: int = 3) -> TestReport:
    """
    Run pytest runs times consecutively. Returns passed=True only if ALL runs pass.
    Any single failure → passed=False, note="flaky". (C1 — flaky fix prevention)

    Args:
        fixture_path: Path to the fixture git repo.
        runs:         Number of consecutive passing runs required.

    Returns:
        TestReport — note="flaky" if any run failed.
    """
    last_report = TestReport(passed=False, failed_tests=[], total=0, exit_code=1, raw="")
    for i in range(runs):
        report = run_tests(fixture_path)
        last_report = report
        if not report.passed:
            log.warning(
                "executor.flaky",
                fixture=str(fixture_path),
                run=i + 1,
                of=runs,
            )
            return TestReport(
                passed=False,
                failed_tests=report.failed_tests,
                total=report.total,
                exit_code=report.exit_code,
                raw=report.raw,
                note="flaky",
            )
    return last_report


def check_regression(before: TestReport, after: TestReport) -> bool:
    """
    Detect if the patch introduced new test failures. (P7)

    Args:
        before: TestReport from before patch was applied.
        after:  TestReport from after patch was applied.

    Returns:
        True if regression detected (new failures introduced), False otherwise.
    """
    regression = len(after.failed_tests) > len(before.failed_tests)

    log.info(
        "regression.check",
        before_failures=len(before.failed_tests),
        after_failures=len(after.failed_tests),
        regression=regression,
    )

    return regression


if __name__ == "__main__":
    import subprocess as sp

    repo_root = Path(__file__).resolve().parents[2]
    fixture = repo_root / "fixtures" / "syn_001"

    # Ensure git repo exists
    if not (fixture / ".git").exists():
        git = ["git", "-C", str(fixture)]
        sp.run([*git, "init", "-q"], check=True)
        sp.run([*git, "config", "user.email", "test@test.com"], check=True)
        sp.run([*git, "config", "user.name", "Test"], check=True)
        sp.run([*git, "config", "core.autocrlf", "false"], check=True)
        sp.run([*git, "config", "core.eol", "lf"], check=True)
        (fixture / ".gitattributes").write_text("* text eol=lf\n")
        sp.run([*git, "add", "."], check=True)
        sp.run([*git, "commit", "-q", "-m", "init"], check=True)

    report = run_tests(fixture)
    print(f"PASS  run_tests: passed={report.passed} total={report.total} failed={len(report.failed_tests)}")

    # Regression check — same report before/after = no regression
    no_reg = check_regression(report, report)
    assert no_reg is False, "same reports should not trigger regression"
    print("PASS  check_regression: same reports = no regression")

    # Simulate regression
    worse = TestReport(
        passed=False,
        failed_tests=["tests/test_basic.py::test_new_failure"],
        total=2,
        exit_code=1,
        raw="",
    )
    reg = check_regression(report, worse)
    assert reg is True, "new failure should trigger regression"
    print("PASS  check_regression: new failure = regression detected")

    print("regression.py smoke test PASSED")
