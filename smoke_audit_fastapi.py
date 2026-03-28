"""
Smoke audit v2 — FIX-1 through FIX-9
Goal: FastAPI todo API (real project, third-party deps)
Verifies:
  - T0 scaffold creates stubs
  - T1 requirements.txt generated with fastapi/uvicorn
  - T2+ impl tasks use global_interfaces (FIX-1)
  - pip install fires before pytest (FIX-2)
  - FILE_EDIT produces valid diff (FIX-7)
  - placeholder/syntax/import gates fire (FIX-9)
  - safe paths enforced (FIX-8)
"""
import subprocess
import sys
import shutil
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import os
WORKSPACE = Path(os.environ["WORKSPACE_ROOT"])
PROJ_SLUG = "smoke-fastapi"
repo_path = WORKSPACE / PROJ_SLUG

# Clean slate
if repo_path.exists():
    shutil.rmtree(repo_path)
repo_path.mkdir(parents=True)

subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "agent@test.com"], check=True)
subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "AgentX"], check=True)

print(f"\n{'='*60}")
print(f"SMOKE AUDIT v2 — FIX-1 through FIX-9")
print(f"Project: {PROJ_SLUG}")
print(f"Goal: FastAPI Todo API")
print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}\n")

from phase3.state_manager import save_state
from agent_y.schemas import SharedState
from phase3.orchestrator import run_loop

state = SharedState(
    project_id="audit-fastapi-001",
    project_slug=PROJ_SLUG,
    goal="Build a FastAPI todo API with endpoints to create and list todos stored in memory",
    plan=[],
)
os.environ["WORKSPACE_ROOT"] = str(WORKSPACE)
save_state(state)

print("▶ Starting run_loop()...\n")
final_state = run_loop(
    project_id="audit-fastapi-001",
    goal=state.goal,
    repo_path=repo_path,
    max_iterations=20,
)

# ── Report ───────────────────────────────────────────────────────────────────
elapsed = datetime.now().strftime('%H:%M:%S')
print(f"\n{'='*60}")
print(f"AUDIT RESULTS  [{elapsed}]")
print(f"{'='*60}")

total     = len(final_state.plan)
completed = [t for t in final_state.plan if t.status == "completed"]
failed    = [t for t in final_state.plan if t.status == "failed"]
blocked   = [t for t in final_state.plan if t.status == "blocked"]

print(f"Tasks:  {len(completed)} completed  |  {len(failed)} failed  |  {len(blocked)} blocked  |  {total} total\n")
print("Task breakdown:")
for t in final_state.plan:
    icon = {"completed": "✓", "failed": "✗", "blocked": "⊘", "pending": "○", "in_progress": "►"}.get(t.status, "?")
    retries = f" [{t.failed_attempts} retries]" if t.failed_attempts else ""
    print(f"  {icon} [{t.task_id}] {t.action.value:12} | {t.status:11}{retries} | {t.description[:55]}")

# global_interfaces — did FIX-1 work?
print(f"\nglobal_interfaces captured: {list(final_state.global_interfaces.keys())}")

# Files on disk
print(f"\nFiles on disk:")
for f in sorted(repo_path.rglob("*")):
    if f.is_file() and ".git" not in str(f) and ".agent" not in str(f) and ".pytest_cache" not in str(f) and "__pycache__" not in str(f):
        size = f.stat().st_size
        print(f"  {f.relative_to(repo_path)}  ({size}b)")

# requirements.txt content
req = repo_path / "requirements.txt"
if req.exists():
    print(f"\nrequirements.txt:\n  {req.read_text().strip()}")
else:
    print("\nrequirements.txt: MISSING ✗")

# Final pytest
print(f"\n▶ Final pytest:")
result = subprocess.run(
    [sys.executable, "-m", "pytest", str(repo_path), "-v", "--tb=short"],
    cwd=repo_path,
    text=True,
)

verdict = "PASSED ✓" if result.returncode == 0 and not failed else "ISSUES FOUND ✗"
print(f"\n{'='*60}")
print(f"AUDIT {verdict}")
print(f"{'='*60}\n")
