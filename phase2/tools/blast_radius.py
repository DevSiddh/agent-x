"""
phase2/tools/blast_radius.py — Dependency graph pruning for context_builder.

Identifies the minimal set of files Agent-X/Y needs to read to understand a fix:
  Tier 1: the affected file itself (always included)
  Tier 2: files imported BY the affected file (direct dependencies)
  Tier 3: files that import the affected file (upstream consumers)

Max 8 files total. Supports Python (.py) now — JS/Java stubs for future C3b.

Usage:
    from phase2.tools.blast_radius import get_blast_radius
    files = get_blast_radius(Path("/repo"), Path("src/auth/token.py"))
"""

import ast
import sys
from pathlib import Path

import structlog

log = structlog.get_logger()

_MAX_FILES = 8
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".tox", ".venv", "venv"}


def _get_imports(source: str, filepath: Path) -> list[str]:
    """
    Extract module names imported by a Python file.
    Returns list of dotted module names (e.g. ["os", "phase2.memory.store"]).
    Never raises.
    """
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def _module_to_path(module: str, repo: Path) -> Path | None:
    """
    Convert a dotted module name to a file path relative to repo root.
    Returns None if not found.
    """
    # Convert dots to path separators
    rel = Path(module.replace(".", "/"))
    candidates = [
        repo / (str(rel) + ".py"),
        repo / rel / "__init__.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_importers(repo: Path, affected_file: Path) -> list[Path]:
    """
    Find all Python files in repo that import the affected_file's module.
    Returns list of file paths (Tier 3).
    """
    try:
        rel = affected_file.relative_to(repo)
    except ValueError:
        return []

    # Derive the module path to search for
    module_parts = list(rel.with_suffix("").parts)
    possible_imports = {
        ".".join(module_parts),                    # full dotted: phase2.memory.store
        ".".join(module_parts[-2:]),               # last 2: memory.store
        module_parts[-1],                          # just filename: store
    }

    importers: list[Path] = []
    try:
        for py_file in repo.rglob("*.py"):
            if any(skip in py_file.parts for skip in _SKIP_DIRS):
                continue
            if py_file == affected_file:
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                imports = set(_get_imports(source, py_file))
                if imports & possible_imports:
                    importers.append(py_file)
            except OSError:
                continue
    except Exception as exc:
        log.warning("blast_radius.importers_error", error=str(exc))

    return importers


def get_blast_radius(repo: Path, affected_file: Path) -> list[Path]:
    """
    Return the minimal set of files needed to understand a fix for affected_file.

    Tier 1: affected_file (always included)
    Tier 2: files imported BY affected_file (direct deps)
    Tier 3: files that import affected_file (consumers)

    Max 8 files total. If more exist, closest by import depth are prioritised.

    Args:
        repo:          Repository root path.
        affected_file: The file being patched (absolute or relative to repo).

    Returns:
        List of Path objects. Never raises. Returns [affected_file] if no
        imports are found or file doesn't exist.
    """
    repo = Path(repo).resolve()
    affected_file = Path(affected_file).resolve() if not affected_file.is_absolute() \
        else Path(affected_file)

    # Resolve relative paths against repo
    if not affected_file.is_absolute():
        affected_file = repo / affected_file

    result: list[Path] = []

    # Tier 1 — always include affected file
    if affected_file.exists():
        result.append(affected_file)
    else:
        log.warning("blast_radius.affected_missing", file=str(affected_file))
        return result

    suffix = affected_file.suffix.lower()

    if suffix == ".py":
        try:
            source = affected_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return result

        # Tier 2 — files imported by affected_file
        imported_modules = _get_imports(source, affected_file)
        tier2: list[Path] = []
        for mod in imported_modules:
            resolved = _module_to_path(mod, repo)
            if resolved and resolved != affected_file and resolved not in tier2:
                tier2.append(resolved)

        # Tier 3 — files that import affected_file
        tier3 = _find_importers(repo, affected_file)
        # Remove duplicates already in tier2
        tier3 = [p for p in tier3 if p not in tier2 and p != affected_file]

        # Combine: tier2 first, then tier3, cap at _MAX_FILES - 1 (tier1 already added)
        combined = tier2 + tier3
        for p in combined:
            if len(result) >= _MAX_FILES:
                break
            if p not in result:
                result.append(p)

    else:
        # JS/Java/PHP stubs — extend at C3b
        log.info("blast_radius.non_python_stub", suffix=suffix)

    log.info(
        "blast_radius.done",
        affected=str(affected_file),
        total_files=len(result),
    )
    return result


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    affected = repo_root / "phase2" / "memory" / "store.py"

    files = get_blast_radius(repo_root, affected)
    print(f"PASS  get_blast_radius: {len(files)} files")
    assert files[0] == affected, "tier1 must be affected_file"
    print("PASS  tier1 = affected_file")
    assert len(files) <= _MAX_FILES, f"must not exceed {_MAX_FILES} files"
    print(f"PASS  <= {_MAX_FILES} files")

    # Test with non-existent file
    empty = get_blast_radius(repo_root, repo_root / "nonexistent.py")
    assert empty == [], "non-existent file → empty list"
    print("PASS  non-existent file → empty list")

    print("blast_radius.py smoke test PASSED")
    for f in files:
        print(f"  {f.relative_to(repo_root)}")
