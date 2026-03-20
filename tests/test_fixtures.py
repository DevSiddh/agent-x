"""
tests/test_fixtures.py
Step 0 — Verify all 5 fixture repos exist, are git repos,
and their synthetic patches apply cleanly via git apply --check.

Patch format in synthetic.jsonl: raw unified diff string (expected_patch field).
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / "phase1" / "dataset" / "synthetic.jsonl"
FIXTURES_ROOT = REPO_ROOT / "fixtures"

CASE_IDS = ["syn_001", "syn_002", "syn_003", "syn_004", "syn_005"]


def load_cases() -> dict[str, dict]:
    cases = {}
    with open(JSONL_PATH) as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                cases[case["id"]] = case
    return cases


CASES = load_cases()


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_fixture_dir_exists(case_id: str) -> None:
    fixture = FIXTURES_ROOT / case_id
    assert fixture.is_dir(), f"fixtures/{case_id}/ does not exist"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_fixture_is_git_repo(case_id: str) -> None:
    fixture = FIXTURES_ROOT / case_id
    git_dir = fixture / ".git"
    assert git_dir.is_dir(), f"fixtures/{case_id}/ is not a git repo (no .git/)"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_fixture_has_committed_state(case_id: str) -> None:
    fixture = FIXTURES_ROOT / case_id
    r = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=fixture, capture_output=True, text=True
    )
    assert r.returncode == 0, f"git log failed in {case_id}"
    assert r.stdout.strip(), f"No commits in {case_id}"


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_patch_applies_cleanly(case_id: str) -> None:
    """Verify the expected_patch from synthetic.jsonl applies to its fixture repo."""
    case = CASES[case_id]
    patch_text = case["expected_patch"]
    fixture = FIXTURES_ROOT / case_id

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".diff", delete=False, newline="\n"
    ) as tf:
        tf.write(patch_text + "\n")
        tmp_path = tf.name

    try:
        r = subprocess.run(
            ["git", "apply", "--check", tmp_path],
            cwd=fixture, capture_output=True, text=True
        )
    finally:
        os.unlink(tmp_path)

    assert r.returncode == 0, (
        f"git apply --check failed for {case_id}:\n{r.stderr.strip()}"
    )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_fixture_has_tests(case_id: str) -> None:
    fixture = FIXTURES_ROOT / case_id
    tests_dir = fixture / "tests"
    assert tests_dir.is_dir(), f"fixtures/{case_id}/tests/ does not exist"
    test_files = list(tests_dir.glob("test_*.py"))
    assert test_files, f"No test_*.py files in fixtures/{case_id}/tests/"


def test_all_case_ids_in_jsonl() -> None:
    """All 5 expected case IDs are present in synthetic.jsonl."""
    for cid in CASE_IDS:
        assert cid in CASES, f"{cid} missing from synthetic.jsonl"


if __name__ == "__main__":
    import subprocess as sp
    sp.run(["pytest", __file__, "-v"])
