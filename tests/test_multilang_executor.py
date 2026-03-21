"""
tests/test_multilang_executor.py
Tests for multi-language executor support (C3).
Covers get_runner() selection and parse_report() for Jest + pytest formats.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from phase2.executor.runner import get_runner
from phase2.executor.regression import parse_report, run_tests, TestReport


# ---------------------------------------------------------------------------
# get_runner — extension → command selection
# ---------------------------------------------------------------------------

def test_get_runner_python():
    cmd = get_runner("main.py")
    assert cmd[0] == sys.executable
    assert "pytest" in cmd


def test_get_runner_javascript():
    cmd = get_runner("app.js")
    assert "jest" in " ".join(cmd)


def test_get_runner_typescript():
    cmd = get_runner("server.ts")
    assert "vitest" in " ".join(cmd)


def test_get_runner_php():
    cmd = get_runner("Controller.php")
    assert "phpunit" in " ".join(cmd)


def test_get_runner_java():
    cmd = get_runner("Main.java")
    assert "mvn" in " ".join(cmd)


def test_get_runner_unknown_falls_back_to_pytest():
    cmd = get_runner("script.rb")
    assert cmd[0] == sys.executable
    assert "pytest" in cmd


def test_get_runner_no_extension_falls_back_to_pytest():
    cmd = get_runner("Makefile")
    assert cmd[0] == sys.executable
    assert "pytest" in cmd


# ---------------------------------------------------------------------------
# parse_report — format normalisation
# ---------------------------------------------------------------------------

def test_parse_report_pytest_format(tmp_path: Path):
    """parse_report handles pytest-json-report format."""
    report = {
        "summary": {"total": 3},
        "tests": [
            {"nodeid": "tests/test_foo.py::test_ok", "outcome": "passed"},
            {"nodeid": "tests/test_foo.py::test_bad", "outcome": "failed"},
        ],
    }
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(report), encoding="utf-8")

    failed, total = parse_report(report_file, "pytest")
    assert total == 3
    assert failed == ["tests/test_foo.py::test_bad"]


def test_parse_report_jest_format(tmp_path: Path):
    """parse_report handles Jest JSON format."""
    report = {
        "numTotalTests": 4,
        "numFailedTests": 1,
        "testResults": [
            {
                "testFilePath": "/project/app.test.js",
                "testResults": [
                    {"fullName": "divide normal", "status": "passed"},
                    {"fullName": "divide by zero throws", "status": "failed"},
                ],
            }
        ],
    }
    report_file = tmp_path / "report.json"
    report_file.write_text(json.dumps(report), encoding="utf-8")

    failed, total = parse_report(report_file, "jest")
    assert total == 4
    assert "divide by zero throws" in failed


def test_parse_report_missing_file(tmp_path: Path):
    """parse_report returns empty result when file does not exist."""
    failed, total = parse_report(tmp_path / "missing.json", "pytest")
    assert failed == []
    assert total == 0


def test_parse_report_malformed_json(tmp_path: Path):
    """parse_report returns empty result on malformed JSON."""
    bad = tmp_path / "report.json"
    bad.write_text("not json", encoding="utf-8")
    failed, total = parse_report(bad, "pytest")
    assert failed == []
    assert total == 0


# ---------------------------------------------------------------------------
# JS fixture — skipped if Node / jest not available
# ---------------------------------------------------------------------------

def _node_available() -> bool:
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not _node_available(), reason="Node.js not installed")
def test_apply_patch_js_fixture_with_jest_runner():
    """Apply fix to syn_js_001 fixture and verify jest runner is selected."""
    repo_root = Path(__file__).resolve().parents[1]
    fixture = repo_root / "fixtures" / "syn_js_001"

    # Initialise git repo if needed
    if not (fixture / ".git").exists():
        git = ["git", "-C", str(fixture)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "config", "user.email", "test@test.com"], check=True)
        subprocess.run([*git, "config", "user.name", "Test"], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "init buggy state"], check=True)

    cmd = get_runner("app.js")
    assert "jest" in " ".join(cmd), "Expected jest runner for .js file"
