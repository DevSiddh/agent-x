"""
phase2/executor/runner.py
Applies unified diff patches to fixture repos via subprocess git apply. (P1 — no openclaw)
All paths use pathlib.Path + cwd= param. (P16)
"""

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import structlog
from pydantic import BaseModel

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Runner map — file extension → test command (C3)
# ---------------------------------------------------------------------------

_RUNNER_MAP: dict[str, list[str]] = {
    ".py":   [sys.executable, "-m", "pytest", "tests/", "--tb=short",
              "--json-report", "--json-report-file=report.json", "-q"],
    ".js":   ["npx", "jest", "--json", "--outputFile=report.json"],
    ".ts":   ["npx", "vitest", "run", "--reporter=json"],
    ".php":  ["phpunit", "--log-json", "report.json"],
    ".java": ["mvn", "test"],
}


def get_runner(affected_file: str) -> list[str]:
    """
    Return the correct test runner command for the given file extension.
    Falls back to pytest for unrecognised extensions.

    Args:
        affected_file: Path or filename with extension (e.g. 'app.js', 'main.py').

    Returns:
        Command list suitable for subprocess.run().
    """
    suffix = Path(affected_file).suffix.lower()
    cmd = _RUNNER_MAP.get(suffix, _RUNNER_MAP[".py"])
    log.info("executor.runner", lang=suffix or ".py", cmd=cmd[0])
    return cmd


class ApplyResult(BaseModel):
    success: bool
    stdout: str
    stderr: str
    error: str


def apply_patch(patch_diff: str, fixture_path: Path) -> ApplyResult:
    """
    Apply a unified diff patch to a fixture repo via git apply.

    Args:
        patch_diff:   Raw unified diff string.
        fixture_path: Path to the fixture git repo.

    Returns:
        ApplyResult — success, stdout, stderr, error message.
    """
    fixture_path = Path(fixture_path).resolve()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".diff", delete=False, newline="\n"
    ) as tf:
        tf.write(patch_diff.strip() + "\n")
        tmp_path = Path(tf.name)

    try:
        result = subprocess.run(
            ["git", "apply", "--ignore-whitespace", "--recount", str(tmp_path)],
            cwd=fixture_path,
            capture_output=True,
            text=True,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    success = result.returncode == 0

    if success:
        log.info("runner.patch_applied", fixture=str(fixture_path))
    else:
        log.warning(
            "runner.patch_failed",
            fixture=str(fixture_path),
            stderr=result.stderr.strip(),
        )

    return ApplyResult(
        success=success,
        stdout=result.stdout,
        stderr=result.stderr,
        error=result.stderr.strip() if not success else "",
    )


def check_syntax(fixture_path: Path, affected_file: str) -> str | None:
    """
    For .py files only: parse with ast.parse() after patch applied.
    Returns error string if SyntaxError, None if clean.
    Costs $0, runs in <1ms — call before pytest to avoid spinning up full suite.
    """
    if not affected_file.endswith(".py"):
        return None
    target = fixture_path / affected_file
    if not target.exists():
        return None
    try:
        ast.parse(target.read_text(encoding="utf-8"))
        return None
    except SyntaxError as exc:
        log.warning(
            "runner.syntax_error",
            file=affected_file,
            line=exc.lineno,
            msg=exc.msg,
        )
        return f"SyntaxError line {exc.lineno}: {exc.msg}"


def rollback(fixture_path: Path) -> None:
    """
    Restore fixture to last committed state.
    git checkout -- . restores tracked files.
    git clean -fd removes untracked files/dirs from failed patches.

    Args:
        fixture_path: Path to the fixture git repo.
    """
    fixture_path = Path(fixture_path).resolve()
    subprocess.run(
        ["git", "checkout", "--", "."],
        cwd=fixture_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=fixture_path,
        capture_output=True,
    )
    log.info("runner.rollback", fixture=str(fixture_path))


if __name__ == "__main__":
    import json

    repo_root = Path(__file__).resolve().parents[2]
    fixture = repo_root / "fixtures" / "syn_001"
    jsonl = repo_root / "phase1" / "dataset" / "synthetic.jsonl"

    # Load syn_001 patch
    with open(jsonl) as f:
        cases = {json.loads(l)["id"]: json.loads(l) for l in f if l.strip()}
    patch_diff = cases["syn_001"]["expected_patch"]

    # Ensure fixture is a git repo
    if not (fixture / ".git").exists():
        print("Initialising fixture git repo...")
        git = ["git", "-C", str(fixture)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "config", "user.email", "test@test.com"], check=True)
        subprocess.run([*git, "config", "user.name", "Test"], check=True)
        subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
        subprocess.run([*git, "config", "core.eol", "lf"], check=True)
        (fixture / ".gitattributes").write_text("* text eol=lf\n")
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "init"], check=True)

    # Rollback to clean state first
    rollback(fixture)

    # Apply patch
    result = apply_patch(patch_diff, fixture)
    assert result.success, f"apply_patch failed: {result.error}"
    print(f"PASS  apply_patch: success={result.success}")

    # Rollback
    rollback(fixture)
    content = (fixture / "requirements.txt").read_text()
    assert "setuptools" not in content, "rollback failed — setuptools still present"
    print("PASS  rollback: file restored to original state")

    print("runner.py smoke test PASSED")
