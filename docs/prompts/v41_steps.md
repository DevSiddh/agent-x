# Agent-X v4.1 | Steps
# Last updated: 2026-03-26
# Goal: idea in → working repo out (end-to-end proven on VPS)

---

## Step Q3 — .agent/context.md committed to GitHub after task

**Problem:** `_commit_context()` exists in orchestrator.py but is only called when
`state.github_repo` is set. In the smoke test / local runs, github_repo is empty → never commits.

**Fix:** Wire `_commit_context` unconditionally when repo_path is a real git repo.
If no remote configured → skip silently. Already handles CalledProcessError gracefully.

**Files to touch:**
- `phase3/orchestrator.py` — check if remote exists before calling `_commit_context`

**Done condition:** After a completed task, `.agent/context.md` is committed to the local repo.
`git log` shows a `[context] update after task T1` commit.

**Test to add:** `tests/test_project_context.py` — mock subprocess, assert commit called after success.

---

## Step E2E — End-to-End Test (v4.1 proof)

**Goal:** Drop a simple brief.yaml → `run_loop()` completes at least 1 task → working file on disk.

**Setup on VPS:**
```bash
cd ~/agent-x
export WORKSPACE_ROOT=/home/agentx/workspaces
mkdir -p $WORKSPACE_ROOT
```

**Brief to use (start minimal):**
```python
# Run this directly in Python REPL on VPS
from pathlib import Path
from agent_y.schemas import SharedState, Task, TaskAction, AcceptanceCriteria, AcceptanceCase

criteria = AcceptanceCriteria(
    target_function="add",
    cases=[
        AcceptanceCase(inputs=["add(2,3)"], expected="5"),
        AcceptanceCase(inputs=["add(0,0)"], expected="0"),
        AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
    ],
)
task = Task(
    task_id="T1",
    action=TaskAction.WRITE_FILE,
    description="Create add() function in src/math_utils.py",
    files_to_touch=["src/math_utils.py", "tests/test_math_utils.py"],
    patch_order=["src/math_utils.py", "tests/test_math_utils.py"],
    acceptance_criteria=criteria,
)
```

**What to do on VPS:**
1. Create a fresh git repo in WORKSPACE_ROOT/smoke_e2e/
2. `git init`, `git commit --allow-empty -m "init"`
3. Run `run_loop()` with goal="build add function" and repo_path pointing to it
4. Watch DeepSeek write src/math_utils.py + tests/test_math_utils.py
5. Check task status = "completed"

**Done condition:**
- Task status = "completed" in state.json
- `src/math_utils.py` exists on disk with real Python code
- `tests/test_math_utils.py` exists and passes when run manually

**If task fails (Best-of-N exhausted):**
- Check what DeepSeek wrote — is the test file missing?
- The loop writes src file first, then test file. If test file write fails → pytest finds no tests → fails.
- Fix: ensure patch_order = [test_file, src_file] (tests first, then impl)

**Known issue to watch:**
- `_run_tests` looks for `repo_path / "tests"` — must exist before pytest runs
- DeepSeek must write the test file as part of the task (it's in patch_order)
- If test file written after src file, pytest runs after src only → no tests found → fails

---

## After E2E passes — what's unlocked

- v4.1 is proven: idea in → working repo out
- Next: connect to brief_watcher.py (drop brief.yaml → auto-triggers run_loop)
- Then: Telegram notification when loop completes
- Then: run on a real project (crypto bot, scraper, CLI tool)
