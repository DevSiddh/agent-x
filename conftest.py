"""
conftest.py — session-scoped setup for Agent-X tests.

Fixture repos (fixtures/syn_001..005/) are tracked as plain directories
in the main repo. This hook initialises them as real git repos before
any test that needs git apply to work.
"""
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = REPO_ROOT / "fixtures"
CASE_IDS = ["syn_001", "syn_002", "syn_003", "syn_004", "syn_005"]


def _init_fixture_repo(path: Path) -> None:
    """Init a fresh git repo in a fixture dir and commit all files."""
    git = ["git", "-C", str(path)]
    if (path / ".git").exists():
        # Migration: add pytest.ini if untracked so detect_runner can find a manifest
        result = subprocess.run(
            [*git, "ls-files", "--others", "--exclude-standard", "pytest.ini"],
            capture_output=True, text=True,
        )
        if result.stdout.strip() == "pytest.ini":
            subprocess.run([*git, "add", "pytest.ini"], check=True)
            subprocess.run(
                [*git, "commit", "-q", "-m", "add pytest.ini for manifest detection"],
                check=True,
            )
        return
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "challayagneshsaisiddhardha@gmail.com"], check=True)
    subprocess.run([*git, "config", "user.name", "CH Y SAI SIDDHARDHA"], check=True)
    subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
    subprocess.run([*git, "config", "core.eol", "lf"], check=True)
    # write .gitattributes to force LF
    (path / ".gitattributes").write_text("* text eol=lf\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init buggy state"], check=True)


def pytest_configure(config: pytest.Config) -> None:
    """Initialise all fixture repos before any test session starts."""
    for case_id in CASE_IDS:
        fixture_path = FIXTURES_ROOT / case_id
        if fixture_path.is_dir():
            _init_fixture_repo(fixture_path)
