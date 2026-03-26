"""E2E smoke test — run_loop() on smoke_e2e project."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from phase3.orchestrator import run_loop
from phase3.state_manager import STATE_PATH

# Always start fresh — delete stale state from previous runs
if STATE_PATH.exists():
    STATE_PATH.unlink()
    print(f"Cleared old state: {STATE_PATH}")

repo_path = Path("/home/agentx/projects/smoke_e2e")

state = run_loop(
    project_id="smoke_e2e",
    goal="build add function",
    repo_path=repo_path,
    max_iterations=10,
)

print("\n--- RESULT ---")
for t in state.plan:
    print(f"  {t.task_id}: {t.status}")
