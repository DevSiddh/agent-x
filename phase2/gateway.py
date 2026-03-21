"""
phase2/gateway.py
Gateway stage — zero-cost direct fixes for well-known patterns.

Runs BEFORE ContextBuilder. If a pattern matches and fix succeeds,
pipeline returns immediately — no Agent-Y, no DeepSeek, zero API cost.

Rules are derived from real memory.jsonl data only (gate: ≥3 occurrences).
Top patterns as of 2026-03-22:
  59x  DependencyError:ModuleNotFoundError:requirements.txt
  13x  ConfigError:no_such_table
  12x  RuntimeError:pydantic_namespace
  11x  EnvironmentError:no_build_isolation

Run smoke test:
    python phase2/gateway.py
"""

import re
import sys
from pathlib import Path
from typing import Callable

import structlog
from pydantic import BaseModel

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class GatewayResult(BaseModel):
    matched_rule: str
    patch_applied: str  # human-readable description of what was changed
    success: bool


# ---------------------------------------------------------------------------
# Fix functions — one per rule
# ---------------------------------------------------------------------------

_MODULE_PATTERN = re.compile(
    r"ModuleNotFoundError: No module named '?([A-Za-z0-9_.-]+)'?", re.I
)


def _fix_module_not_found(error_lines: list[str], fixture_path: Path) -> str | None:
    """
    Extract missing module from ModuleNotFoundError and append to requirements.txt.
    Returns patch description or None if fix cannot be applied.
    """
    module_name: str | None = None
    for line in error_lines:
        m = _MODULE_PATTERN.search(line)
        if m:
            module_name = m.group(1).split(".")[0]  # top-level package only
            break

    if not module_name:
        return None

    req_path = fixture_path / "requirements.txt"

    if not req_path.exists():
        req_path.write_text(f"{module_name}\n", encoding="utf-8")
        log.info("gateway.fix.module_not_found", action="created", module=module_name)
        return f"created requirements.txt with {module_name}"

    existing = req_path.read_text(encoding="utf-8")

    # Already present (any version specifier) → gateway cannot help
    if re.search(
        rf"^{re.escape(module_name)}([>=<\[\s]|$)",
        existing,
        re.MULTILINE | re.I,
    ):
        log.info("gateway.fix.module_not_found", action="already_present", module=module_name)
        return None

    req_path.write_text(existing.rstrip() + f"\n{module_name}\n", encoding="utf-8")
    log.info("gateway.fix.module_not_found", action="appended", module=module_name)
    return f"appended {module_name} to requirements.txt"


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

class _Rule:
    def __init__(self, name: str, pattern: re.Pattern, fix: Callable) -> None:
        self.name = name
        self.pattern = pattern
        self.fix = fix


GATEWAY_RULES: list[_Rule] = [
    # Rule 1 — ModuleNotFoundError → add to requirements.txt
    # Source: top memory pattern — 59x real occurrences
    _Rule(
        name="module_not_found",
        pattern=re.compile(r"ModuleNotFoundError: No module named", re.I),
        fix=_fix_module_not_found,
    ),
]


# ---------------------------------------------------------------------------
# Public check function
# ---------------------------------------------------------------------------

def check(error_lines: list[str], fixture_path: Path) -> GatewayResult | None:
    """
    Try each gateway rule against error_lines.

    If a rule matches and fix applies successfully → return GatewayResult.
    If no match or fix returns None → return None (fall through to full pipeline).

    Args:
        error_lines:   Cleaned log lines from LogParser / log_cleaner_real.
        fixture_path:  Local path to git repo fixture.

    Returns:
        GatewayResult if a fix was applied, None otherwise.
    """
    full_text = "\n".join(error_lines)
    log.info("gateway.check", rules=len(GATEWAY_RULES), lines=len(error_lines))

    for rule in GATEWAY_RULES:
        if rule.pattern.search(full_text):
            log.info("gateway.match", rule=rule.name)
            patch_desc = rule.fix(error_lines, fixture_path)
            if patch_desc is not None:
                log.info("gateway.applied", rule=rule.name, patch=patch_desc)
                return GatewayResult(
                    matched_rule=rule.name,
                    patch_applied=patch_desc,
                    success=True,
                )
            log.info("gateway.fix_skipped", rule=rule.name, reason="fix_returned_none")

    log.info("gateway.miss", reason="no_rule_matched")
    return None


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    print("=== Gateway Smoke Test ===")

    # Test 1: creates requirements.txt when missing
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        result = check(["ModuleNotFoundError: No module named 'pandas'"], fixture)
        assert result is not None, "Expected gateway hit"
        assert result.matched_rule == "module_not_found"
        assert result.success is True
        assert (fixture / "requirements.txt").read_text(encoding="utf-8").strip() == "pandas"
        print("  PASS  Test 1: created requirements.txt with pandas")

    # Test 2: appends to existing requirements.txt
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        (fixture / "requirements.txt").write_text("requests==2.0.0\n", encoding="utf-8")
        result = check(["ModuleNotFoundError: No module named 'numpy'"], fixture)
        content = (fixture / "requirements.txt").read_text(encoding="utf-8")
        assert result is not None
        assert "numpy" in content
        assert "requests" in content
        print("  PASS  Test 2: appended numpy, preserved requests")

    # Test 3: module already present → gateway miss
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        (fixture / "requirements.txt").write_text("pandas==2.0.0\n", encoding="utf-8")
        result = check(["ModuleNotFoundError: No module named 'pandas'"], fixture)
        assert result is None, "Expected None — module already present"
        print("  PASS  Test 3: module already present → gateway miss")

    # Test 4: no matching pattern → None
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        result = check(["AssertionError: discount 150 > 100"], fixture)
        assert result is None
        print("  PASS  Test 4: no match → None")

    print("\ngateway.py smoke test PASSED")
    sys.exit(0)
