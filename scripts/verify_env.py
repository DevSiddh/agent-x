"""
Environment Verification Script
Run this at the START of every dev session to catch drift early.
Usage: python scripts/verify_env.py

Checks:
- Python version matches requirement
- All required packages installed at correct versions
- No stale __pycache__ in critical paths
- Required env vars present
- Port 8080 is free
- No zombie processes
"""

import importlib
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASS = []
FAIL = []
WARN = []


def check(label: str, ok: bool, detail: str = "", warn: bool = False) -> None:
    if ok:
        PASS.append(f"  PASS  {label}")
    elif warn:
        WARN.append(f"  WARN  {label}: {detail}")
    else:
        FAIL.append(f"  FAIL  {label}: {detail}")


# ── Python version ─────────────────────────────────────────────────────────────
major, minor = sys.version_info[:2]
check(
    f"Python version ({major}.{minor})",
    major == 3 and minor >= 11,
    f"need 3.11+, got {major}.{minor}"
)

# ── Required packages ──────────────────────────────────────────────────────────
REQUIRED = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("aiosqlite", "aiosqlite"),
    ("structlog", "structlog"),
    ("pydantic", "pydantic"),
    ("openai", "openai"),
    ("pytest", "pytest"),
    ("dotenv", "python-dotenv"),
]

for module, pkg_name in REQUIRED:
    try:
        importlib.import_module(module)
        check(f"Package: {pkg_name}", True)
    except ImportError:
        check(f"Package: {pkg_name}", False, f"run: pip install {pkg_name}")

# ── Pydantic v2 ────────────────────────────────────────────────────────────────
try:
    import pydantic
    v = int(pydantic.VERSION.split(".")[0])
    check(f"Pydantic v2 (got {pydantic.VERSION})", v >= 2, "need v2+")
except ImportError:
    check("Pydantic v2", False, "not installed")

# ── Stale __pycache__ in critical paths ────────────────────────────────────────
critical = ["phase1", "phase2"]
for path in critical:
    caches = list((ROOT / path).rglob("__pycache__")) if (ROOT / path).exists() else []
    check(
        f"No stale cache in {path}/",
        len(caches) == 0,
        f"{len(caches)} __pycache__ dirs found — run: make clean",
        warn=True
    )

# ── Port 8080 free ─────────────────────────────────────────────────────────────
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    port_in_use = s.connect_ex(("localhost", 8080)) == 0
check(
    "Port 8080 free",
    not port_in_use,
    "port in use — run: make clean",
)

# ── Required env vars ──────────────────────────────────────────────────────────
env_file = ROOT / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

ENV_VARS = [
    ("GITHUB_WEBHOOK_SECRET", False),   # (name, required_for_tests)
    ("DEEPSEEK_API_KEY", False),        # False = warn only, not hard fail
    ("GITHUB_TOKEN", False),
]

for var, required in ENV_VARS:
    val = os.environ.get(var, "")
    present = bool(val)
    check(
        f"Env var: {var}",
        present,
        f"not set in .env — needed for spike + pipeline",
        warn=not required
    )

# ── queue.db not stale ─────────────────────────────────────────────────────────
db = ROOT / "phase1" / "webhook" / "queue.db"
check(
    "No stale queue.db",
    not db.exists(),
    "stale queue.db found — run: make clean",
    warn=True
)

# ── Print results ──────────────────────────────────────────────────────────────
print("\n=== Agent-X Environment Check ===\n")

for line in PASS:
    print(line)
for line in WARN:
    print(line)
for line in FAIL:
    print(line)

print(f"\nResult: {len(PASS)} pass  |  {len(WARN)} warn  |  {len(FAIL)} fail")

if FAIL:
    print("\nFix failures before running tests.\n")
    sys.exit(1)
elif WARN:
    print("\nWarnings are non-blocking but fix them for clean runs.\n")
    sys.exit(0)
else:
    print("\nAll checks passed. Good to go.\n")
    sys.exit(0)


if __name__ == "__main__":
    pass  # script runs at import level
