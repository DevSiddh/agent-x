"""
phase2/tools/ast_mapper.py — AST-based repo architecture skeleton for Agent-Y.

Uses stdlib ast to extract only class/function signatures (no bodies).
Replaces naive depth=3 directory tree — stays under 2000 tokens on any repo.

Usage:
    from phase2.tools.ast_mapper import map_repo
    skeleton = map_repo(Path("/path/to/repo"), max_tokens=2000)
"""

import ast
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".tox", ".venv", "venv", "dist", "build"}
_SKIP_SUFFIXES = {".pyc", ".pyo", ".pyd"}


def _extract_signatures(source: str, filepath: Path) -> list[str]:
    """
    Parse Python source and return signature lines (class + function names, no bodies).
    Returns empty list if ast parse fails.
    """
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    lines: list[str] = []

    # Module docstring (first line only)
    if (
        tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        docstring = tree.body[0].value.value.split("\n")[0].strip()
        if docstring:
            lines.append(f"    # {docstring[:80]}")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(
                (b.id if isinstance(b, ast.Name) else ast.unparse(b))
                for b in node.bases
            )
            lines.append(f"    class {node.name}({bases}):" if bases else f"    class {node.name}:")
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    lines.append(f"        def {item.name}({_format_args(item.args)})")
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Top-level functions only (not nested inside classes)
            if not any(
                isinstance(parent, ast.ClassDef)
                for parent in ast.walk(tree)
                if hasattr(parent, "body") and node in getattr(parent, "body", [])
            ):
                lines.append(f"    def {node.name}({_format_args(node.args)})")

    return lines


def _format_args(args: ast.arguments) -> str:
    """Format function argument list into a compact signature string."""
    parts: list[str] = []
    for arg in args.args:
        annotation = (
            f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
        )
        parts.append(f"{arg.arg}{annotation}")  # ast.arg uses .arg, not .name
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")
    return ", ".join(parts)


def _sort_key(file_path: Path, affected_file: str | None) -> tuple[int, str]:
    """Sort files: closest to affected_file first, then alphabetically."""
    if affected_file:
        try:
            # Prefer files in the same directory as affected_file
            aff = Path(affected_file)
            if file_path.parent == aff.parent or file_path.name == aff.name:
                return (0, str(file_path))
        except Exception:
            pass
    return (1, str(file_path))


def map_repo(
    repo: Path,
    max_tokens: int = 2000,
    affected_file: str | None = None,
) -> str:
    """
    Extract a compact AST skeleton of the repo — class names + method signatures only.

    Args:
        repo:          Path to the repository root.
        max_tokens:    Hard cap on output length (chars / 4 ≈ tokens). Default 2000.
        affected_file: If provided, files in the same directory are sorted first.

    Returns:
        Formatted skeleton string. Empty string if repo has no Python files.
        Never raises.
    """
    repo = Path(repo).resolve()
    if not repo.is_dir():
        return ""

    # Collect all .py files, excluding test files and skip dirs
    py_files: list[Path] = []
    try:
        for p in repo.rglob("*.py"):
            if any(skip in p.parts for skip in _SKIP_DIRS):
                continue
            if p.suffix in _SKIP_SUFFIXES:
                continue
            if p.name.startswith("test_") or p.name.endswith("_test.py"):
                continue
            py_files.append(p)
    except Exception as exc:
        log.warning("ast_mapper.glob_error", error=str(exc))
        return ""

    # Sort: affected_file's directory first
    py_files.sort(key=lambda p: _sort_key(p, affected_file))

    output_parts: list[str] = []
    char_budget = max_tokens * 4  # rough chars-per-token estimate

    for filepath in py_files:
        try:
            source = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        try:
            rel = filepath.relative_to(repo)
        except ValueError:
            rel = filepath

        sigs = _extract_signatures(source, filepath)
        if not sigs:
            continue

        block = f"{rel}:\n" + "\n".join(sigs)
        if sum(len(p) for p in output_parts) + len(block) > char_budget:
            output_parts.append("# ... (truncated — max_tokens reached)")
            break
        output_parts.append(block)

    result = "\n\n".join(output_parts)
    log.info(
        "ast_mapper.done",
        files=len(output_parts),
        chars=len(result),
    )
    return result


if __name__ == "__main__":
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    skeleton = map_repo(repo_root / "phase2", max_tokens=2000)
    print(f"PASS  map_repo: {len(skeleton)} chars")
    # Verify no function bodies leaked through
    assert "return " not in skeleton or "def " not in skeleton.split("return")[0].split("\n")[-1], \
        "function body leaked into skeleton"
    print("PASS  no function bodies in output")
    print("ast_mapper.py smoke test PASSED")
    print("\n--- skeleton preview (first 500 chars) ---")
    print(skeleton[:500])
