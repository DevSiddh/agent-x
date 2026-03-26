"""
phase2/executor/runner.py
Applies unified diff patches to fixture repos via subprocess git apply. (P1 — no openclaw)
All paths use pathlib.Path + cwd= param. (P16)
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import structlog
from pydantic import BaseModel

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Manifest-based runner detection (C3b)
# ---------------------------------------------------------------------------

class RunnerDetectionError(Exception):
    """Raised when no test runner manifest is found in the fixture tree."""


_PYTEST_CMD: list[str] = [
    sys.executable, "-m", "pytest", "tests/", "--tb=short",
    "--json-report", "--json-report-file=report.json", "-q",
]


def _check_manifest(directory: Path) -> tuple[list[str], Path] | None:
    """
    Check for a test runner manifest in directory.
    Returns (runner_cmd, execution_root) or None if no manifest found.
    Priority: package.json → pyproject.toml/pytest.ini → tox.ini → pom.xml → build.gradle → Makefile
    """
    pkg_json = directory / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            test_script = pkg.get("scripts", {}).get("test", "")
            if "vitest" in test_script:
                return ["npx", "vitest", "run", "--reporter=json"], directory
        except Exception:
            pass
        return ["npx", "jest", "--json", "--outputFile=report.json"], directory

    if (directory / "pyproject.toml").exists() or (directory / "pytest.ini").exists():
        return _PYTEST_CMD, directory

    if (directory / "tox.ini").exists():
        return _PYTEST_CMD, directory

    if (directory / "pom.xml").exists():
        return ["mvn", "test"], directory

    if (directory / "build.gradle").exists() or (directory / "build.gradle.kts").exists():
        return ["./gradlew", "test"], directory

    if (directory / "Makefile").exists():
        return ["make", "test"], directory

    # Fallback: tests/ directory present → assume pytest (Python convention)
    if (directory / "tests").is_dir():
        return _PYTEST_CMD, directory

    return None


def detect_runner(fixture_path: str, affected_file: str) -> tuple[list[str], Path]:
    """
    Detect the correct test runner by walking up from the affected file's
    directory to the fixture root, checking for manifest files.

    Manifest priority: package.json → pyproject.toml/pytest.ini → tox.ini
                       → pom.xml → build.gradle → Makefile

    Args:
        fixture_path:  Root of the fixture git repo.
        affected_file: Path to the file that was patched (absolute or relative).

    Returns:
        Tuple of (runner_command, execution_root_path).

    Raises:
        RunnerDetectionError: No manifest found in the fixture tree.
    """
    fp = Path(fixture_path).resolve()
    af = Path(affected_file)

    # Determine starting directory within the fixture
    if af.is_absolute():
        try:
            start_dir = (fp / af.relative_to(fp)).parent.resolve()
        except ValueError:
            start_dir = fp
    else:
        start_dir = (fp / af.parent).resolve()

    # Clamp to fixture root (never walk above it)
    if not str(start_dir).startswith(str(fp)):
        start_dir = fp

    # Walk up from start_dir to fp
    current = start_dir
    while True:
        result = _check_manifest(current)
        if result is not None:
            cmd, exec_root = result
            log.info("executor.runner_detected", exec_root=str(exec_root), runner=cmd[0])
            return cmd, exec_root

        if current == fp:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent

    raise RunnerDetectionError(
        f"No test runner manifest found in {fp} (searched from {start_dir})"
    )


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


class RunResult(BaseModel):
    """Result of a write_file() call."""
    success: bool
    error: str = ""


def write_file(
    file_path: Path,
    content: str,
    repo_path: Path,
) -> RunResult:
    """
    Write new file content to disk.
    Steps:
      1. Validate 50-line limit
      2. Create parent directories if missing
      3. Write content to file_path
      4. git add file_path (subprocess, cwd=repo_path)
      5. Return RunResult(success=True)
    Never raises. All errors → RunResult(success=False, error=str(e)).
    structlog: executor.write_file.ok / executor.write_file.error
    """
    try:
        lines = content.splitlines()
        if len(lines) > 150:
            log.warning(
                "executor.write_file.error",
                file=str(file_path),
                lines=len(lines),
                reason="exceeds 150-line limit",
            )
            return RunResult(success=False, error="write_file: exceeds 150-line limit")

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        subprocess.run(
            ["git", "add", str(file_path)],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
        log.info("executor.write_file.ok", file=str(file_path), lines=len(lines))
        return RunResult(success=True)
    except Exception as exc:
        log.error("executor.write_file.error", file=str(file_path), error=str(exc))
        return RunResult(success=False, error=str(exc))


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
        ["git", "reset", "HEAD", "--", "."],
        cwd=fixture_path,
        capture_output=True,
    )
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
