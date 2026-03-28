"""
Smoke audit — FIX-1 through FIX-4
Goal: simple calculator (add function)
Verifies: T0 scaffold → T1 requirements.txt → T2 impl all execute correctly
"""
import subprocess
import sys
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Setup a clean temp project dir under WORKSPACE_ROOT
import os
WORKSPACE = Path(os.environ["WORKSPACE_ROOT"])
PROJ_SLUG = "smoke-calc"
repo_path = WORKSPACE / PROJ_SLUG

# Clean slate
if repo_path.exists():
    shutil.rmtree(repo_path)
repo_path.mkdir(parents=True)

# Init git repo
subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "agent@test.com"], check=True)
subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "AgentX"], check=True)

print(f"\n{'='*60}")
print(f"SMOKE AUDIT — FIX-1 through FIX-4")
print(f"Project: {PROJ_SLUG}")
print(f"Path: {repo_path}")
print(f"{'='*60}\n")

# Wire up orchestrator
from phase3.state_manager import save_state
from agent_y.schemas import SharedState
from phase3.orchestrator import run_loop

state = SharedState(
    project_id="smoke-001",
    project_slug=PROJ_SLUG,
    goal="Create a calculator module with add, subtract, multiply functions",
    plan=[],
)
os.environ["WORKSPACE_ROOT"] = str(WORKSPACE)
save_state(state)

print("▶ Starting run_loop()...\n")
final_state = run_loop(
    project_id="smoke-001",
    goal=state.goal,
    repo_path=repo_path,
    max_iterations=15,
)

# ── Report ──────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("AUDIT RESULTS")
print(f"{'='*60}")

total     = len(final_state.plan)
completed = [t for t in final_state.plan if t.status == "completed"]
failed    = [t for t in final_state.plan if t.status == "failed"]
blocked   = [t for t in final_state.plan if t.status == "blocked"]
pending   = [t for t in final_state.plan if t.status == "pending"]

print(f"Tasks total:     {total}")
print(f"  ✓ completed:   {len(completed)}")
print(f"  ✗ failed:      {len(failed)}")
print(f"  ⊘ blocked:     {len(blocked)}")
print(f"  ○ pending:     {len(pending)}")

print(f"\nTask breakdown:")
for t in final_state.plan:
    icon = {"completed": "✓", "failed": "✗", "blocked": "⊘", "pending": "○", "in_progress": "►"}.get(t.status, "?")
    print(f"  {icon} [{t.task_id}] {t.action:12} | {t.status:11} | {t.description[:50]}")

# Check files on disk
print(f"\nFiles on disk in {repo_path}:")
for f in sorted(repo_path.rglob("*")):
    if f.is_file() and ".git" not in str(f) and ".agent" not in str(f):
        size = f.stat().st_size
        print(f"  {f.relative_to(repo_path)}  ({size}b)")

# Final pytest run on the project
print(f"\n▶ Final pytest on project:")
result = subprocess.run(
    [sys.executable, "-m", "pytest", str(repo_path), "-v", "--tb=short"],
    cwd=repo_path,
    capture_output=False,
    text=True,
)
print(f"\nPytest exit code: {result.returncode}")
print(f"\n{'='*60}")
print(f"AUDIT {'PASSED ✓' if result.returncode == 0 and len(failed) == 0 else 'ISSUES FOUND ✗'}")
print(f"{'='*60}\n")
