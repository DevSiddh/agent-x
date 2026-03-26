"""
tests/test_multilang_executor.py
Tests for multi-language executor support (C3b).
Covers detect_runner() manifest-based selection and parse_report() for Jest + pytest formats.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from phase2.executor.runner import detect_runner, RunnerDetectionError
from phase2.executor.regression import parse_report, run_tests, PatchTestReport


# ---------------------------------------------------------------------------
# detect_runner — manifest-based selection
# ---------------------------------------------------------------------------

def test_detect_runner_python_via_pytest_ini(tmp_path: Path) -> None:
    """detect_runner returns pytest when pytest.ini is present."""
    (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")
    cmd, exec_root = detect_runner(str(tmp_path), "main.py")
    assert sys.executable in cmd
    assert "pytest" in cmd
    assert exec_root == tmp_path


def test_detect_runner_python_via_pyproject_toml(tmp_path: Path) -> None:
    """detect_runner returns pytest when pyproject.toml is present."""
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    cmd, exec_root = detect_runner(str(tmp_path), "app/main.py")
    assert "pytest" in cmd
    assert exec_root == tmp_path


def test_detect_runner_javascript_via_package_json(tmp_path: Path) -> None:
    """detect_runner returns jest when package.json with jest script is present."""
    pkg = {"name": "test", "scripts": {"test": "jest"}, "devDependencies": {"jest": "^29"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    cmd, exec_root = detect_runner(str(tmp_path), "app.js")
    assert "jest" in " ".join(cmd)
    assert exec_root == tmp_path


def test_detect_runner_vitest_via_package_json(tmp_path: Path) -> None:
    """detect_runner returns vitest when package.json test script uses vitest."""
    pkg = {"name": "test", "scripts": {"test": "vitest run"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    cmd, exec_root = detect_runner(str(tmp_path), "server.ts")
    assert "vitest" in " ".join(cmd)
    assert exec_root == tmp_path


def test_detect_runner_java_via_pom_xml(tmp_path: Path) -> None:
    """detect_runner returns mvn when pom.xml is present."""
    (tmp_path / "pom.xml").write_text("<project/>")
    cmd, exec_root = detect_runner(str(tmp_path), "Main.java")
    assert "mvn" in cmd
    assert exec_root == tmp_path


def test_detect_runner_walks_up_to_root(tmp_path: Path) -> None:
    """detect_runner walks up from nested affected_file to find manifest at root."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    nested = tmp_path / "src" / "utils"
    nested.mkdir(parents=True)
    (nested / "helper.py").write_text("")
    cmd, exec_root = detect_runner(str(tmp_path), "src/utils/helper.py")
    assert "pytest" in cmd
    assert exec_root == tmp_path


def test_detect_runner_raises_when_no_manifest(tmp_path: Path) -> None:
    """detect_runner raises RunnerDetectionError when no manifest found."""
    with pytest.raises(RunnerDetectionError):
        detect_runner(str(tmp_path), "script.rb")


def test_detect_runner_makefile_as_fallback(tmp_path: Path) -> None:
    """detect_runner returns make test when only Makefile is present."""
    (tmp_path / "Makefile").write_text("test:\n\tpytest\n")
    cmd, exec_root = detect_runner(str(tmp_path), "script.py")
    assert "make" in cmd
    assert exec_root == tmp_path


# ---------------------------------------------------------------------------
# parse_report — format normalisation
# ---------------------------------------------------------------------------

def test_parse_report_pytest_format(tmp_path: Path) -> None:
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


def test_parse_report_jest_format(tmp_path: Path) -> None:
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


def test_parse_report_missing_file(tmp_path: Path) -> None:
    """parse_report returns empty result when file does not exist."""
    failed, total = parse_report(tmp_path / "missing.json", "pytest")
    assert failed == []
    assert total == 0


def test_parse_report_malformed_json(tmp_path: Path) -> None:
    """parse_report returns empty result on malformed JSON."""
    bad = tmp_path / "report.json"
    bad.write_text("not json", encoding="utf-8")
    failed, total = parse_report(bad, "pytest")
    assert failed == []
    assert total == 0


# ---------------------------------------------------------------------------
# run_tests — no runner returns PatchTestReport with note="no_runner"
# ---------------------------------------------------------------------------

def test_run_tests_no_manifest_returns_no_runner_note(tmp_path: Path) -> None:
    """run_tests returns note='no_runner' when no manifest is found in fixture."""
    # tmp_path has no manifest files
    report = run_tests(tmp_path, "app.rb")
    assert report.note == "no_runner"
    assert report.passed is False


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
def test_apply_patch_js_fixture_detect_runner() -> None:
    """detect_runner finds jest via package.json in syn_js_001 fixture."""
    repo_root = Path(__file__).resolve().parents[1]
    fixture = repo_root / "fixtures" / "syn_js_001"
    assert (fixture / "package.json").exists(), "syn_js_001 must have package.json"

    cmd, exec_root = detect_runner(str(fixture), "app.js")
    assert "jest" in " ".join(cmd), "Expected jest runner for .js file"
    assert exec_root == fixture.resolve()
