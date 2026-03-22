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


def parse_report(report_path: Path, runner: str) -> tuple[list[str], int]:
    """
    Parse a test report file into (failed_test_ids, total_count).
    Handles both pytest-json-report and Jest JSON formats.

    Args:
        report_path: Path to the JSON report file.
        runner:      Runner name (e.g. "pytest", "jest", "npx").

    Returns:
        Tuple of (failed_test_names, total_count).
    """
    if not report_path.exists():
        return [], 0

    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], 0

    failed: list[str] = []
    total = 0

    # Jest JSON format: {"testResults": [...], "numTotalTests": N, "numFailedTests": N}
    if "testResults" in data:
        total = data.get("numTotalTests", 0)
        for suite in data.get("testResults", []):
            for test in suite.get("testResults", []):
                if test.get("status") == "failed":
                    failed.append(test.get("fullName") or test.get("title", "unknown"))

    # pytest-json-report format: {"summary": {...}, "tests": [...]}
    elif "tests" in data:
        total = data.get("summary", {}).get("total", 0)
        for test in data["tests"]:
            if test.get("outcome") == "failed":
                failed.append(test.get("nodeid", "unknown"))

    else:
        log.warning("regression.unknown_report_format", runner=runner, keys=list(data.keys()))

    return failed, total


def run_tests(fixture_path: Path, affected_file: str = "") -> TestReport:
    """
    Run the appropriate test suite on a fixture repo and return structured results.
    Detects runner from affected_file extension (C3). Falls back to pytest.

    Args:
        fixture_path:  Path to the fixture git repo.
        affected_file: File that was patched — used to select correct test runner.

    Returns:
        TestReport with passed, failed_tests, total, exit_code, raw output.
    """
    from phase2.executor.runner import get_runner

    fixture_path = Path(fixture_path).resolve()
    report_file = fixture_path / "report.json"
    cmd = get_runner(affected_file)

    # Inject report file path for runners that support it
    cmd_with_report = [
        arg.replace("report.json", str(report_file)) for arg in cmd
    ]

    result = subprocess.run(
        cmd_with_report,
        cwd=fixture_path,
        capture_output=True,
        text=True,
    )

    runner_name = cmd[0].split("/")[-1].split("\\")[-1]
    failed_tests, total = parse_report(report_file, runner_name)
    report_file.unlink(missing_ok=True)

    passed = result.returncode == 0

    log.info(
        "regression.test_run",
        fixture=str(fixture_path),
        runner=runner_name,
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
    last_passing: TestReport | None = None
    for i in range(runs):
        report = run_tests(fixture_path)
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
        last_passing = report
    # last_passing is non-None: all `runs` iterations passed
    assert last_passing is not None
    return last_passing


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
