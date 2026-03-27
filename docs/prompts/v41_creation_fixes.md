# Agent-X v4.1 | Creation Mode — Gap Analysis
# Source: Runnable audit + Gemini review (docs/runable+gemini.md)
# Last updated: 2026-03-27
# Tests: 657 passing — v4.1 proven on simple tasks only
# Goal of this file: understand WHAT is broken and WHY before touching any code

---

## THE CORE PROBLEM

v4.1 works on toy projects (single function, 1 file).
It fails on real projects (FastAPI app, Telegram bot, CLI tool).
Not because the architecture is wrong — because of 9 execution gaps.
Every gap is fixable. None require redesign.

The ceiling today:
- Agent-X writes Task 2 not knowing what Task 1 built
- pytest runs before dependencies are installed
- No folder structure → imports fail before tests even start
- FILE_EDIT sends raw LLM text instead of a diff → always fails

---

## PRIORITY MAP

```
TIER 1 — Breaks every real project (highest priority)
  FIX-1: L2/L9  global_interfaces not injected into prompt     (5 lines)
  FIX-2: L3     pip install missing before pytest               (10 lines)
  FIX-3: A1     no scaffold task T0 — blank directory start     (30 lines)

TIER 2 — Breaks mid-complexity projects
  FIX-4: L7     no requirements.txt generation in plan          (prompt change)
  FIX-5: A3     plan_goal() ignores context.md on resume        (10 lines)
  FIX-6: L10    replan() fires with empty failed_diff           (15 lines)

TIER 3 — Breaks advanced features
  FIX-7: A5     file_edit sends raw text not unified diff       (30 lines)
  FIX-8: B4     resolve_safe_path() missing on some writes      (audit)
  FIX-9: L5     placeholder code not detected before pytest     (15 lines)

REJECTED — do not build
  Async API calls  violates VPS sequential constraint (1 vCPU)
  Line limit 300   defeats task decomposition discipline
  Obsidian brain   visualization, not critical path — v4.2
```

---

## TIER 1 — DETAILED ANALYSIS

---

### FIX-1 — global_interfaces never injected
**Files:** phase3/orchestrator.py → _build_agent_x_prompt()
**Source:** Runnable L2 + L9

**What is broken:**
ast_mapper.py runs after every task and extracts class/function signatures into
state.global_interfaces. The data is there. But _build_agent_x_prompt() never reads it.
Agent-X writes every task with zero knowledge of what previous tasks built.

Example failure:
- Task 1 writes models.py → class User(Base), class Todo(Base)
- Task 2 writes routes.py → tries to import User but guesses wrong module path
- pytest: ImportError — even though models.py exists and is correct

**Why it is a 5-line fix:**
The data exists in state.global_interfaces (a dict: filename → list of signatures).
_build_agent_x_prompt() already receives the task and state.
The only missing piece: format the dict as a text block and append it to the prompt.

**What changes:**
- Only _build_agent_x_prompt() is touched
- No schema changes, no new files, no new logic
- If global_interfaces is empty (Task 1): nothing added — zero cost

**Impact:** Every Task 2+ goes from blind to informed. Biggest ROI of all fixes.

---

### FIX-2 — pip install missing before pytest
**Files:** phase3/orchestrator.py → _run_tests()
**Source:** Runnable L3

**What is broken:**
_run_tests() calls pytest immediately after writing files.
If the project imports fastapi, sqlalchemy, httpx — they must be installed first.
Currently: no install step exists. Result: ModuleNotFoundError from pytest import phase,
which looks identical to a logic bug. Agent-X retries 3 times thinking its code is wrong.
The code was correct. The package was just not installed.

**Why this matters:**
stdlib projects (just using os, pathlib, json) work fine today.
Any real project with third-party imports: fails at import time before tests run.
FIX-3 (scaffold) will generate requirements.txt. FIX-2 installs it.
Both are needed together for real projects.

**What changes:**
- Only _run_tests() is touched
- Add: if (repo_path / "requirements.txt").exists() → run uv pip install before pytest
- Use uv always (VPS rule: global cache, no venv bloat per project)
- Fall back to pip if uv not found (portability)
- Log the install step

**Constraint locked by VPS rules:**
Use uv for all dependency management. No per-project venv. Global cache only.

---

### FIX-3 — no scaffold task T0
**Files:** phase3/orchestrator.py → _execute_file_ops() + agent_y/reasoner.py → CREATION_SYSTEM_PROMPT
**Source:** Runnable A1 + Gemini "C-Header Hack"

**What is broken:**
CLAUDE.md says "T0 = scaffold task always first". It is not implemented.
TaskAction.SCAFFOLD exists in schemas.py but _execute_file_ops() never handles it.
Every project starts from a blank directory. No folder structure. No __init__.py.
pytest cannot discover tests without __init__.py in tests/.
Imports fail between files because Python can't find the packages.

**The C-Header Hack (Gemini's name for this pattern):**
Write ALL project files as stubs first — just the function/class names with pass bodies.
Then fill them in task by task.
Because stubs exist from T0, every later task can safely import from them.
"file doesn't exist yet" crash class: eliminated entirely.

**What changes — two parts:**

Part 1 — orchestrator.py:
Add branch in _execute_file_ops(): if task.action == TaskAction.SCAFFOLD →
call a new _execute_scaffold() function that:
  - Creates all directories from files_to_touch
  - Writes "# filename — stub\n" to each file
  - Creates __init__.py in every new directory automatically
  - git adds all stubs
  - Returns True without calling DeepSeek or running pytest

Part 2 — CREATION_SYSTEM_PROMPT:
Add rule: Agent-Y must always emit T0 with action=SCAFFOLD containing all planned files.
T0 has no acceptance criteria (no tests for stubs).
After T0: emit tasks in topological dependency order.

**Why topological order matters:**
models.py has no internal dependencies → write first
schemas.py imports from models.py → write second
routes.py imports from both → write third
If Agent-Y emits these in wrong order: even with stubs, imports fail.
Adding the topological rule to CREATION_SYSTEM_PROMPT: ~10 lines of prompt text, zero code.

**Impact:** After FIX-3:
- Folder structure guaranteed before any code is written
- __init__.py in every directory automatically
- Every task can import from every other task's stub
- The "file doesn't exist" class of errors: gone

---

## TIER 2 — DETAILED ANALYSIS

---

### FIX-4 — no requirements.txt in plan
**Files:** agent_y/reasoner.py → CREATION_SYSTEM_PROMPT
**Source:** Runnable L7

**What is broken:**
Agent-Y plans tasks but never generates a requirements.txt task.
FIX-2 runs pip install before pytest — but only if requirements.txt exists.
Without this fix, FIX-2 is a no-op for projects where Agent-Y forgets the file.

**What changes:**
Prompt engineering only. No code.
Add to CREATION_SYSTEM_PROMPT: always include T1 = create requirements.txt.
Agent-Y infers packages from the goal (FastAPI goal → fastapi, uvicorn, pydantic).
T1 comes after T0 scaffold, before any implementation.

**Why not harder than it sounds:**
Agent-Y already knows the goal. It can infer dependencies.
The only missing piece: the instruction to always generate this task.

---

### FIX-5 — plan_goal() ignores context.md on resume
**Files:** phase3/orchestrator.py → run_loop(), agent_y/reasoner.py → reason()
**Source:** Runnable A3

**What is broken:**
When resuming a failed project, plan_goal() starts from scratch.
It ignores .agent/context.md which has: goal, architecture, key files, decisions, last task.
Result: every resume generates a completely new plan from Task 1.
If the project was 80% done, resume overwrites the done tasks and starts over.
Duplicate files, conflicting code, broken state.

**What changes:**
run_loop(): before calling reason(), read .agent/context.md if it exists.
Pass it to reason() as an additional_context string.
reason(): inject this block into the prompt so Agent-Y knows what's already built.

read_context() already exists in project_context.py — zero new infrastructure.

---

### FIX-6 — replan() fires with empty context
**Files:** phase3/orchestrator.py → run_once() failure path
**Source:** Runnable L10

**What is broken:**
When failed_task_streak hits 2, replan() is triggered.
replan() takes a failed_diff parameter — what Agent-X last wrote that failed.
The orchestrator never passes this. replan() gets empty string.
Agent-Y replans without knowing what was tried → same plan → same failure → infinite loop.

This is the most dangerous gap: it looks like the system is working (replan fires, new plan generated)
but the replan contains no real information and produces identical output.

**What changes:**
_execute_file_ops(): capture the last DeepSeek output even on failure.
Return it alongside the bool success flag.
run_once() failure path: pass last_failed_content to replan().

replan() signature already accepts failed_diff. The data just never reaches it.

---

## TIER 3 — DETAILED ANALYSIS

---

### FIX-7 — file_edit broken by design
**Files:** phase3/orchestrator.py → FILE_EDIT branch in _execute_file_ops()
**Source:** Runnable A5

**What is broken:**
FILE_EDIT tasks call apply_patch(content, repo_path) where content is raw DeepSeek output.
apply_patch() expects a unified diff (--- a/file / +++ b/file header).
Raw LLM output is never a unified diff. Every FILE_EDIT task fails.
Currently zero edit tasks have succeeded in real runs — they just haven't been tested because
real projects haven't been attempted.

**The right approach:**
Do not ask DeepSeek to generate a diff — it can't do it reliably.
Instead: ask DeepSeek for the complete new file content.
Then generate the diff ourselves using Python's difflib.unified_diff.
Apply the generated diff. This is deterministic and reliable.

**What changes:**
FILE_EDIT branch: read original file → call DeepSeek for full new content →
generate diff with difflib → apply with apply_patch.
If diff is empty (no changes): return True silently (not an error).

---

### FIX-8 — resolve_safe_path() not everywhere
**Files:** phase3/orchestrator.py → _execute_file_ops()
**Source:** Runnable B4

**What is broken:**
resolve_safe_path() exists and raises on path traversal attacks (../../etc/passwd).
But some code paths in _execute_file_ops() construct file paths from DeepSeek output
without calling resolve_safe_path() first.
On a VPS with internet-facing webhook: this is a real security gap, not theoretical.

**What changes:**
Audit every line in _execute_file_ops() that constructs or uses a file path.
Every path from task input must go through resolve_safe_path(repo_path, file_str) before use.
This is a read-only audit + targeted additions — no logic changes.

---

### FIX-9 — placeholder code reaches pytest
**Files:** phase3/orchestrator.py → between _call_deepseek() and write_file()
**Source:** Runnable L5

**What is broken:**
For complex tasks DeepSeek sometimes returns:
  def add(a, b):
      # TODO: implement this
      pass
No validation catches this. The stub gets written. pytest runs. All tests fail.
Agent-X retries 3 times with "tests failed" as rejection reason — but the real reason
is that the implementation was never written. The retry prompt is wrong.

**What changes:**
Add _is_placeholder(content) check between DeepSeek response and write_file().
Simple heuristics: # TODO + pass blocks, all-pass file, under 3 lines of actual code.
If placeholder detected: return False immediately → triggers retry with correct reason.
Retry prompt then says "your previous response was a placeholder stub, not an implementation."

---

## WHAT THESE FIXES UNLOCK TOGETHER

```
After FIX-1 + FIX-2 alone:
  Multi-file projects where files are stdlib-only → work
  Agent-X Task 2 knows what Task 1 built

After + FIX-3:
  Folder structure automatic
  __init__.py automatic
  The "file not found at import" crash class: gone

After + FIX-4:
  Third-party dependencies installed automatically
  FastAPI, sqlalchemy, httpx projects: work end-to-end

After + FIX-5:
  Project resume works (doesn't start over)
  10-task projects can fail at task 5 and continue from task 6

After + FIX-6:
  Replan has actual context → different strategy → not infinite loop

After + FIX-7/8/9:
  Edit tasks work
  Security gap closed
  Placeholder code triggers correct retry

FINAL STATE:
  Drop brief.yaml for FastAPI CRUD app → complete working repo
  Drop brief.yaml for Telegram bot → complete working repo
  Drop brief.yaml for CLI tool → complete working repo
  This is the real v4.1. Not "add() function". Real projects.
```

---

## WHAT IS DEFERRED AND WHY

| Idea | Source | Decision | Reason |
|------|--------|----------|--------|
| Async API calls | Gemini | REJECTED | VPS = 1 vCPU, sequential only — locked constraint |
| Line limit 300 | Gemini | REJECTED | 50/15 limits enforce task decomposition — raising hides bad plans |
| Obsidian glass brain | Gemini | PARKED v4.2 | Visualization, not on critical path |
| Project template system | Runnable A2 | PARKED v4.2 | Needs real project variety first |
| OpenAI embeddings API | Gemini | DONE | BM25 already in production (657 tests) |
| ONNX quantization | Gemini | DONE | BM25 already solved the RAM problem |
