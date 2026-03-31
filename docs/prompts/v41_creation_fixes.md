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
  FIX-1: L2/L9  _run_ast_mapper scope + global_interfaces injection + SkillVault wiring (~15 lines)
  FIX-2: L3+G   pip install + Surgical Pytest (-x --ff + timeout tiers) (~15 lines)
  FIX-3: A1     no scaffold task T0 — blank directory start     (30 lines)

TIER 2 — Breaks mid-complexity projects
  FIX-4: L7     no requirements.txt generation in plan          (prompt change)
  FIX-5: A3     plan_goal() ignores context.md on resume        (10 lines)
  FIX-6: L10    replan() never fires + empty failed_diff when it does  (~13 lines)

TIER 3 — Breaks advanced features
  FIX-7: A5     file_edit sends raw text not unified diff       (30 lines)
  FIX-8: B4     resolve_safe_path() missing on some writes      (audit)
  FIX-9: L5     placeholder code not detected before pytest     (15 lines)

TIER 4 — Unlocks Devin-like test quality + diagnostic reasoning (gated: after FIX-3/FIX-9)
  FIX-17: dynamic test generation — TEST_FRAMEWORK_MAP + conftest.py per project_type (~80 lines)
  FIX-18: agentic RAG for creation mode — creation_context_builder.py adapts existing context_builder (~30 lines)

REJECTED — do not build
  Async API calls  violates VPS sequential constraint (1 vCPU)
  Line limit 300   defeats task decomposition discipline
  Obsidian brain   visualization, not critical path — v4.2
```

---

## TIER 1 — DETAILED ANALYSIS

---

### FIX-1 — global_interfaces never injected + _run_ast_mapper wrong scope + SkillVault disconnected
**Files:** phase3/orchestrator.py → _build_agent_x_prompt() + _run_ast_mapper()
**Source:** Runnable L2 + L9 + 2026-03-28 audit

**What is broken — 3 connected gaps in the same function chain:**

Gap A — _run_ast_mapper() maps wrong scope:
_run_ast_mapper() calls map_repo(fp.parent) — maps the ENTIRE parent directory, not just the file.
If task touches models.py and routes.py (same dir): full directory skeleton stored twice under
two different keys. By task 8, global_interfaces contains duplicate bloated data.
Fix: call _extract_signatures() directly on the specific file, not map_repo() on its parent.

Gap B — global_interfaces never injected into prompt:
After Gap A is fixed, global_interfaces has correct per-file signatures.
But _build_agent_x_prompt() never reads state.global_interfaces.
Agent-X writes every task with zero knowledge of what previous tasks built.
Fix: format global_interfaces as a text block, append to prompt.

Example failure without FIX-1:
- Task 1 writes models.py → class User(Base), class Todo(Base)
- Task 2 writes routes.py → guesses wrong import path for User
- pytest: ImportError — even though models.py exists and is correct

Gap C — SkillVault initialized but never used:
orchestrator.py creates SkillVault() and sets used_skill_ids = [] but nothing appends to it.
vault.get_context_block(goal) is never called — zero reusable patterns reach Agent-X.
Fix: call vault.get_context_block(task.description) in _build_agent_x_prompt(),
inject result as a Skills section. If vault empty (first run): nothing added, zero cost.

**What changes — ~15 lines, orchestrator.py only:**

Part 1 — fix _run_ast_mapper() (~5 lines):
Replace map_repo(fp.parent) with direct per-file signature extraction.
Result: global_interfaces = {"models.py": ["class User(Base)", "class Todo(Base)"], ...}

Part 2 — inject global_interfaces into _build_agent_x_prompt() (~5 lines):
If global_interfaces non-empty: format as "## What exists so far" block → append to prompt.
If empty (Task 1): skip — zero cost, no empty section injected.

Part 3 — wire SkillVault.get_context_block() into _build_agent_x_prompt() (~3 lines):
Call vault.get_context_block(task.description) → if non-empty → append as "## Reusable patterns".
SkillVault already exists, already works, already has BM25 search. Just not called.

NOTE — RUN_TESTS dead enum:
TaskAction.RUN_TESTS exists in schemas.py but Agent-Y never emits it and orchestrator
never handles it. No action needed. Document as dead value — remove at v4.2 cleanup.

**Impact:** Every Task 2+ goes from triple-blind (no interfaces, no skills, no patterns)
to triple-informed. Biggest ROI of all fixes. Size grows 5 → ~15 lines, still Tier 1.

---

### FIX-2 — pip install missing before pytest + Surgical Pytest (merged FIX-19)
**Files:** phase3/orchestrator.py → _run_tests()
**Source:** Runnable L3 + Gemini 2026-03-28

**What is broken (Part 1 — install):**
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

**What is broken (Part 2 — Surgical Pytest):**
_run_tests() already targets the task's test file when one is in files_to_touch.
But it is missing three things:
1. `-x` (fail fast): pytest runs all failures even when the first is enough — wastes time + floods logs
2. `--ff` (failed first): on retry, pytest does not prioritise the test that just failed
3. Full suite gate: tasks with no test file fall back to `pytest .` (full repo) — wrong trigger point

Without these: a 3-retry bug on a project with 40 tests takes minutes per retry instead of seconds.
The feedback loop collapses on any real project.

**NOTE — existing code already does file-level targeting:**
```python
# orchestrator.py:343 — already exists, not broken, just incomplete
test_files = [f for f in task.files_to_touch if f.startswith("test_")]
if test_files:
    pytest_target = str(repo_path / test_files[0])  # ← file-level, correct
else:
    pytest_target = str(repo_path)  # ← falls back to full repo — fix this
```

**What changes — _run_tests() only, ~15 lines total:**

```python
def _run_tests(repo_path: Path, task: Task) -> bool:
    import os
    # Part 1 — install dependencies before running any tests
    req = repo_path / "requirements.txt"
    if req.exists():
        installer = "uv" if _uv_available() else "pip"
        cmd = [installer, "pip", "install", "-r", str(req)] if installer == "uv" \
              else [sys.executable, "-m", "pip", "install", "-r", str(req)]
        subprocess.run(cmd, cwd=repo_path, capture_output=True, check=False)

    # Part 2 — Surgical Pytest: 3-tier targeting
    test_files = [f for f in task.files_to_touch if f.startswith("test_")]
    if test_files:
        # Tier 1 — micro-loop: file-level, fail fast, failed first
        target = str(repo_path / test_files[0])
        timeout = int(os.environ.get("TEST_TIMEOUT_FILE", "30"))
        cmd = [sys.executable, "-m", "pytest", target, "-x", "--ff", "--tb=short", "-q"]
    else:
        # No test file in this task (scaffold, requirements.txt, config)
        # Skip pytest — next task's test will catch issues
        # Full suite runs only at iteration audit (FIX-13 trigger)
        return True

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        log.warning("orchestrator.test_failed",
                    stdout=result.stdout[-600:], stderr=result.stderr[-200:])
    return result.returncode == 0
```

**.env.example additions:**
```
TEST_TIMEOUT_FILE=30      # seconds per file-level test run (retries stay fast)
TEST_TIMEOUT_FULL=600     # seconds for full suite at iteration audit (FIX-13)
```

**3-tier structure — how it maps to the full architecture:**
```
Tier 1 — Micro-loop (this fix):
  file-level targeting + -x --ff → retries take seconds not minutes
  already implemented for targeting; adding fail-fast flags only

Tier 2 — Domain merge (FIX-15):
  after domain completes → run pytest tests/domain_a/ before moving to Domain B
  FIX-15 already plans this; _run_tests() timeout = TEST_TIMEOUT_FILE × domain_size

Tier 3 — Full suite release (FIX-13):
  after ALL tasks complete → iteration audit triggers pytest . with TEST_TIMEOUT_FULL
  only time the full suite runs — not during retries, not between tasks
```

**Why NOT pytest-xdist (parallel):**
2GB VPS. Parallel workers + database fixtures = OOM crash. Sequential only. Locked.

**Constraint locked by VPS rules:**
Use uv for all dependency management. No per-project venv. Global cache only.

**Pre-build risk audit (2026-03-28):**
Current _run_tests() state vs spec — exact collision map:

| Item | Current | Action |
|------|---------|--------|
| test_files targeting | EXISTS (line 374) | keep — do not rewrite |
| -q --tb=short flags | EXISTS | keep |
| -x --ff flags | MISSING | add to cmd |
| timeout=60 hardcoded | WRONG — spec uses TEST_TIMEOUT_FILE env var | replace |
| else: pytest_target = str(repo_path) | WRONG — spec says return True | replace |
| try/except wrapper | EXISTS — spec omits it but it is correct | keep |
| pip install block | MISSING entirely | add above pytest logic |
| _uv_available() helper | MISSING — only in spec | add above _run_tests() |
| .env.example timeout vars | MISSING | add after code |

Exact edit plan (3 edits, one file + one config):
1. Add _uv_available() helper directly above _run_tests()
2. Replace _run_tests() body — keep try/except shell, replace everything inside
3. Add TEST_TIMEOUT_FILE=30 and TEST_TIMEOUT_FULL=600 to .env.example

Spec code block is correct as-is — paste inside existing try/except, do not strip it.

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

### FIX-6 — replan() never fires + fires with empty context when it does
**Files:** phase3/orchestrator.py → run_loop() + run_once() failure path
**Source:** Runnable L10 + 2026-03-28 audit

**What is broken — 2 layers:**

Layer A — replan() is never triggered (the real bug):
When failed_task_streak hits 2, run_once() does this:
  log.info("orchestrator.streak_2 — Agent-Y replan needed")  ← just a log message
  state = mark_failed(state, task.task_id, "streak_limit")
  return state                                              ← returns, replan never called

run_loop() only calls plan_goal() when plan is EMPTY. After streak==2, plan is NOT empty
(there are still pending tasks). So plan_goal() is never triggered either.

Result: streak hits 2 → task marked failed → run_once() returns → run_loop() calls
run_once() again → next pending task ALSO immediately hits streak==2 check → also
marked failed without running → all remaining tasks cascade-fail. Build dies silently.

Layer B — when replan fires, failed_diff is empty:
replan() accepts failed_diff: str — what Agent-X last wrote that failed.
Even after fixing Layer A, the orchestrator captures no failed content to pass.
Agent-Y replans blind → same plan → same failure → true infinite loop.

This is the most dangerous gap: it LOOKS like replan fires (log says so) but nothing
actually happens. The build silently dies or loops forever.

**What changes — 2 parts:**

Part 1 — add replan trigger to run_loop() (~8 lines):
After run_once() returns, check if failed_task_streak == 2.
If yes: call replan() with last_failed_content → replace remaining plan tasks.
Reset failed_task_streak to 0 after replan so new sub-tasks get fresh attempts.
Max replan count = 2 (already locked in hard rules).

Part 2 — capture failed content in run_once() (~5 lines):
_execute_file_ops(): capture last DeepSeek output even on failure.
Surface it back through run_once() return value or state field.
run_loop() passes it to replan() in Part 1.

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

**What changes — three gates before write_file():**
```
Gate 1 — Placeholder check (original FIX-9):
  _is_placeholder(content): regex catches TODO/pass stubs
  If placeholder → reject immediately, retry with correct reason

Gate 2 — Syntax check (expanded from REVIEW 6):
  ast.parse(content): catches syntax errors before pytest boots
  If SyntaxError → reject, retry with "your code has a syntax error"
  Zero RAM, zero API cost, faster than pytest

Gate 3 — Import validation (expanded from REVIEW 6):
  if task_number > 1 and global_interfaces not empty:
    check all import statements against global_interfaces
    if import not found → reject, retry with "X does not exist yet"
  SKIP on task 1 (global_interfaces empty — nothing to validate against)
```

All three gates run before write_file(). If any fails → reject + correct retry reason.
Pytest remains gate 4 — logic correctness, unchanged.

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

---

---

### FIX-3b — Template Scaffold Library (enhances FIX-3)

**Files:**
- templates/fastapi_crud/         NEW — proven FastAPI CRUD structure
- templates/telegram_bot/         NEW — proven Telegram bot structure
- templates/cli_tool/             NEW — proven CLI tool structure
- templates/manifest.yaml         NEW — template index + tags
- phase3/orchestrator.py          MOD — match_template() called before scaffold
- phase3/plan_checkpoint.py       MOD — show template match in plan display

**What is broken:**
FIX-3 scaffold creates stub files (pass-only bodies, correct structure).
Agent-X still generates all boilerplate from scratch: main.py setup, database.py,
requirements.txt, conftest.py. DeepSeek invents these every time.
Result: wrong imports, wrong patterns, structural retries on code that never changes
project to project.

**What changes:**
Before scaffold runs, attempt template match on goal string.
Match found: copy template files as base → Agent-X only generates custom logic.
No match: fall back to FIX-3 stub approach (unchanged).

Template match is keyword-based, zero API calls, zero cost.
Minimum 2 tag matches required before template is used.
User always sees plan at Plan Checkpoint — template match shown as:
"Matched FastAPI CRUD template. Only generating your custom logic."

**Templates organized by NICHE (domain-first, not tech-first):**
```
crypto/
  price_feed       tags: crypto, price, feed, websocket, ccxt, binance
  trading_bot      tags: crypto, trading, strategy, order, exchange, bot
  portfolio        tags: crypto, portfolio, pnl, multi-exchange, tracker

stocks/
  screener         tags: stocks, equity, screener, yfinance, signal, alert
  backtester       tags: stocks, backtest, pandas, ta-lib, strategy

polymarket/
  market_bot       tags: polymarket, prediction, odds, market, bet, position

web/
  fastapi_crud     tags: fastapi, crud, rest, api, endpoint, sqlalchemy
  dashboard        tags: dashboard, streamlit, charts, live, data, ui

bots/
  telegram_bot     tags: telegram, bot, message, command, handler
  discord_bot      tags: discord, bot, slash, command, embed

data/
  pipeline         tags: pipeline, etl, scraper, data, csv, transform
```

RAG fallback when no template matches:
  BM25 queries memory.jsonl with goal keywords + failure_category
  Top 3 accepted patterns injected into Agent-Y prompt as context
  Agent-Y generates informed plan instead of blank canvas
  Plan shown at Plan Checkpoint — user always confirms

Templates use {{placeholder}} for custom parts only:
  {{model_name}}, {{command_name}}, {{project_name}}
Everything else is proven boilerplate — never generated by DeepSeek.

**Fallback (always safe):**
No template match → FIX-3 stub approach → Plan Checkpoint asks user:
"No template for this project type. Here's my plan — does this look right?"

**Impact:**
~40% fewer DeepSeek calls per project (boilerplate files pre-filled).
Structural errors (wrong imports, wrong paths) on common project types: gone.
Covers 80% of real project requests with 3 templates.

**Build gate:** after FIX-3 is working and tested.
**Size:** ~50 lines new code + 3 template directories.

---

## LOOP CONTROL LAYER — FIX-11 + FIX-12 (after FIX-9)

These two fixes form one coherent system: user control over the build loop.
FIX-11 = control BEFORE build. FIX-12 = control DURING build.
Build FIX-11 first. FIX-12 depends on interrupt_queue structure from FIX-11.

---

### FIX-11 — Plan Checkpoint + User Type UX

**Files:**
- phase3/orchestrator.py        → add plan checkpoint at start of run_loop()
- agent_y/reasoner.py           → add interpret_plan_for_user()
- phase3/telegram_bot.py        → plan display + inline buttons + timer
- phase3/schemas.py             → add plan_approved: bool + user_type: str to SharedState
- NEW: phase3/plan_checkpoint.py → format plan, detect user type, timer logic (~40 lines)

**What is broken:**
Agent-Y plans → Orchestrator immediately starts executing. No pause. No user review.
If Agent-Y misunderstood the brief, 30 minutes of API calls are wasted before user sees output.
User has no chance to catch wrong assumptions before building starts.

**What changes:**

plan_checkpoint.py — four functions:
```
detect_user_type(goal: str) → "technical" | "general"
  technical keywords (FastAPI, SQLAlchemy, endpoint, pytest) → technical
  plain language → general

format_plan_technical(plan) → str
  T1: models.py — User, Todo (SQLAlchemy)
  T2: routes.py — CRUD endpoints
  [✅ Build] [✏️ Change] — 10 min timer

format_plan_general(plan) → str
  ✅ Core (always built): Todo list, save to database
  🔵 Optional (your choice): User login (recommended), Email reminders
  No reply in 10 mins → building core + recommended, skipping rest
  [✅ All] [🔵 Core + recommended] [⚡ Core only]

run_checkpoint(plan, state) → bool
  send formatted plan to Telegram
  wait PLAN_APPROVAL_TIMEOUT seconds (default 600 — configurable in .env)
  ✅ approve   → return True
  ✏️ change    → call replan() with user instruction → show plan again (loop max 3)
  no response  → mark task.required=False tasks as SKIPPED → return True
```

orchestrator.py — one addition to run_loop():
```python
# after plan_goal(), before first task:
approved = run_checkpoint(state.plan, state)
# approved is always True (timeout also returns True with skips applied)
```

Timer defaults:
```
task.required = True  → always built, timer has no effect
task.required = False → timeout → SKIPPED (conservative, always safe)
PLAN_APPROVAL_TIMEOUT = 600  (10 min — add to .env.example)
```

**Size:** ~60 lines total. No logic changes to existing loop.
**Done condition:** pytest passes + Telegram mock shows correct plan format for technical and general briefs.

---

### FIX-12 — Mid-task Interrupt Handler

**Files:**
- phase3/orchestrator.py          → _check_interrupts() called before every task
- phase3/schemas.py               → TaskStatus.SKIPPED + interrupt_queue: list[str] in SharedState
- phase3/telegram_bot.py          → pipe all incoming messages → state.interrupt_queue
- NEW: phase3/interrupt_handler.py → intent parser + cascade skip (~40 lines)

**What is broken:**
Every AI coding agent today (Claude Code, Codex, OpenClaw) ignores mid-task user messages.
Message arrives while agent is executing → queued → read only after current action completes → too late.
User says "skip auth, it already exists" → auth gets built anyway.
Root cause: no task boundaries. One big execution block. No interrupt window.

Agent-XYZ has task boundaries by design (50-line atomic tasks).
The gap between tasks is a natural, free interrupt window. It is not being used.

**What changes:**

interrupt_handler.py — three functions:
```
parse_intent(message: str) → dict
  "stop"              → {action: STOP}
  "skip X" / "X exists" / "don't build X"  → {action: SKIP, keyword: "X"}
  "change X to Y"     → {action: MODIFY, instruction: "..."}
  anything else       → {action: CONTINUE}

cascade_skip(state, keyword: str) → None
  find all tasks where keyword in description.lower()
  mark them SKIPPED
  find all tasks with depends_on containing any SKIPPED task_id → also SKIPPED
  log: "Skipped T4 (auth), T5 (middleware — depends on T4)"

check_interrupts(state) → dict
  drain state.interrupt_queue (list of pending Telegram messages)
  parse each → return highest priority intent
  priority: STOP > SKIP > MODIFY > CONTINUE
```

orchestrator.py — loop change:
```python
# before every task execution:
intent = check_interrupts(state)
if intent["action"] == "STOP":
    report_halt(state)
    break
elif intent["action"] == "SKIP":
    cascade_skip(state, intent["keyword"])
    continue  # re-evaluate next pending task
elif intent["action"] == "MODIFY":
    surgical_replan(state, intent["instruction"])
# CONTINUE → fall through to normal execution
```

TaskStatus enum addition:
```python
class TaskStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    DONE        = "done"
    FAILED      = "failed"
    BLOCKED     = "blocked"
    SKIPPED     = "skipped"   # ← new
```

Completion report format:
```
Build complete.
✅ Built:   T1 models, T2 routes, T3 tests (3 tasks)
⏭️ Skipped: T4 auth (user request), T5 middleware (depends on T4)
📦 Pushed:  agent-x/fix-abc123
```

**Why this is a moat:**
Other agents: monolithic execution, no task boundaries → cannot interrupt mid-build by design.
Agent-XYZ: atomic 50-line tasks → interrupt window exists between every task → free.
This is an architectural advantage, not a feature bolt-on.

**Size:** ~70 lines total.
**Done condition:** pytest passes + test that SKIP message cascades correctly to dependent tasks.

**Git milestone checkpoint (added from REVIEW 6):**
After iteration audit passes → git tag milestone-{n}
If next iteration fails catastrophically → git reset --hard milestone-{n}
Zero new infrastructure. Blast radius fully contained per milestone.

---

---

### FIX-14 — Multi-language Backend Support

**Files:**
- phase3/schemas.py              → add language: str = "python" to SharedState
- phase3/orchestrator.py         → _run_tests() + FIX-2 installer become language-aware
- phase3/plan_checkpoint.py      → warn user if Tier 2/3 language selected
- templates/manifest.yaml        → add language tag to each template

**What is missing:**
brief.yaml has no language field. Agent-Y always assumes Python.
_run_tests() in creation mode calls pytest directly — not wired to multi-language executor.
FIX-2 (install deps) assumes requirements.txt + uv pip install — Python only.
Multi-language executor EXISTS from v2.1.6 but is not connected to creation mode pipeline.

**Why this is NOT an architectural fork:**
Exit code is the universal truth signal: 0 = green, non-zero = red.
pytest, jest, go test all return exit code. Thompson Sampling + Best-of-N read exit code only.
Zero changes needed to Thompson, Best-of-N, DecisionEngine — they are already language-agnostic.
The entire "fork" is a dict lookup in _run_tests() and a language-aware FIX-2.

**What changes:**

FIX-2 becomes language-aware (same fix, wider scope):
```
python     → uv pip install -r requirements.txt
nodejs     → npm install
go         → go mod tidy
typescript → npm install
```

_run_tests() dynamic router (wires existing multi-language executor):
```
python     → pytest --json-report
nodejs     → npm test
go         → go test ./...
typescript → npm test
```

Agent-X prompt gets language injected (FIX-1 mechanism, same approach):
  Python → writes def test_foo(): assert ...
  Node.js → writes it('should...', () => { expect(...).toBe(...) })
  AcceptanceCriteria schema unchanged — I/O cases are language-agnostic strings.

Plan Checkpoint warns on Tier 2, redirects on Tier 3/4.

**Language tiers (locked):**
```
Tier 1 (build now):       python, nodejs
Tier 2 (warn + proceed):  go, typescript
Tier 3 (warn + redirect): rust, ruby, php, java, csharp
```

**Size:** ~20 lines total. Dict lookup + language field in schema + prompt injection.
**Gate:** after FIX-3b template library exists (needs template language tags).

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

---

---

### FIX-15 — Domain Splintering (Topological Sort Architecture)
**Origin:** User's idea — session 2026-03-27 (explored via Merge Sort + Quick Sort → resolved to Topological Sort)
**Gate:** After FIX-9 is done and passing. Do not attempt before.

**The Problem it solves:**
Linear orchestration (Task1→Task2→...→Task40) compounds failure probability.
At 90% per-task success: 0.90^40 = 1.5% end-to-end success on 25-file projects.
Domain Splintering resets the compound probability per domain, not per project.

**Why Topological Sort (not Merge Sort or Quick Sort):**
```
Merge Sort alone:   splits into equal chunks (5-6 files) — predictable size
                    BUT ignores dependency order — Domain B might need a file
                    that ended up in Domain C by accident

Quick Sort alone:   pivot = most-imported file, build it first
                    BUT chunk sizes vary wildly (2 files vs 15 files)
                    AND Agent-Y must predict the pivot before files exist

Topological Sort:   the parent algorithm both are approximating
                    Step 1 — Agent-Y predicts full dependency graph from brief
                              (FastAPI: models.py has most imports pointing to it)
                    Step 2 — Topological sort determines BUILD ORDER of all files
                              (most-depended-upon file always built first)
                    Step 3 — Slice into equal chunks of 5-6 files (Merge Sort sizing)
                              preserving topological order within each chunk
                    Step 4 — Each chunk = one domain, built in dependency order

Result: domain SIZE is bounded (Merge Sort) + domain ORDER is dependency-correct
        (Quick Sort pivot) + no accidental cross-domain import failures
```

**Viva sentence:** "Agent-Y runs topological sort on the dependency DAG predicted
from the brief, then slices into equal domains. Domain order = dependency order.
Domain size = bounded complexity. DeepSeek never sees more than 6 files at once."

**How it works:**
```
Plan phase (two-stage Agent-Y — same model, two sequential calls):
  Call 1: brief → full file list + predicted dependency edges
  Call 2: file list + edges → topological sort → slice into domains of 5-6 files
           output: domains[] with build order + dependency graph

  Example (FastAPI CRUD, 20 files):
    Domain A: config.py, database.py, models.py    (no deps — foundation)
    Domain B: schemas.py, crud.py, auth.py         (depends on A signatures)
    Domain C: routes.py, middleware.py, deps.py    (depends on A+B signatures)
    Domain D: main.py, tests/, requirements.txt    (imports all — glue)

Build phase: each domain = isolated mini-project
  Domain A: build → 4-gate check → pytest → extract AST signatures → ✅
  Context boundary (free — just control global_interfaces contents)
  Domain B: receives only Domain A .pyi signatures → build → pytest → ✅
  Context boundary
  Domain C: receives Domain A+B signatures only → build → pytest → ✅
  Context boundary
  Domain D: receives all signatures → integration test → ✅
```

**Math improvement:**
```
Old (linear):  0.90^40 = 1.5%   end-to-end
New (domains): 0.90^6  = 53%    per domain × human checkpoint between domains
```

**What changes:**
- SharedState gets `domains: list[Domain]` alongside `plan: list[Task]`
- Agent-Y CREATION_SYSTEM_PROMPT: two-stage planning (file list → domain split)
- Orchestrator: outer domain loop wraps existing task loop — inner loop UNCHANGED
- Human checkpoint (FIX-11) shown between every domain, not just at start
- No new agent needed — two-stage Agent-Y is same model, two API calls

**Context boundary — it's free, not a new mechanism:**
Agent-X is stateless — every DeepSeek API call is already a fresh context window.
"Context wipe" = just control what global_interfaces contains at domain boundaries.
Domain B receives only Domain A's AST signatures, never Domain A's full source files.
FIX-1 already controls this. Zero new code needed for context isolation.

**Backward compatibility — zero regression:**
Simple project (<10 files) → Agent-Y emits 1 domain → outer loop runs once
→ behavior identical to today's linear loop → no existing tests break.

**Cons — properly specced:**

Con 1: Circular dependency deadlock
  Problem: Agent-Y predicts bad dependency graph — Domain B depends on C, C on B.
           Topological sort fails. Build never starts. No error raised.
  Fix: DAG validation at Plan Checkpoint (FIX-11), BEFORE first domain build:
    ```python
    def validate_domain_dag(domains: list[Domain]) -> bool:
        # DFS cycle detection on domain dependency graph
        # if cycle found → return False
    # cycle detected → reject plan
    # Telegram: "Circular dependency between Domain B and C — replanning"
    # ask Agent-Y to replan domain split → max 2 replans → then human redesigns
    ```
  Size: ~15 lines DFS. Runs at Plan Checkpoint only.

Con 2: Integration failure (semantic vs syntax mismatch)
  Problem: Domain A builds save_trade(price: float). Domain D calls save_trade(trade_data: dict).
           Both pass isolated pytest. Integration test fails. Which domain is wrong?
           Auto-editing either domain risks breaking its own isolated tests.
  Fix: Structured failure flow using FIX-12 interrupt mechanism:
    ```
    Integration test fails →
      Telegram: "Integration failed.
                 Error: save_trade() expected float, got dict.
                 Domain A owns it. Domain D calls it.
                 Which domain to fix? Reply: A / B / C / D"
      Orchestrator pauses (FIX-12 already has pause/resume)
      User replies "A" →
      Orchestrator reopens Domain A tasks from the broken interface
      Domain A rebuilt → AST re-extracted → retry integration test
      Max 2 integration retries → human takeover, orchestrator halts
    ```
  Rule: orchestrator NEVER auto-edits a completed domain without user instruction.
  FIX-12 interrupt handler already has the pause/resume mechanism — just wire it here.

**Prerequisite:** ast_mapper.py already exists (phase2/tools/ast_mapper.py). FIX-1 must be done first — it fixes _run_ast_mapper() scope and injects global_interfaces. Without FIX-1, domain signatures cannot be passed between domains correctly.
**Size:** ~75 lines total — outer domain loop (~30) + DAG validation (~15) + integration failure flow (~30 wired to FIX-12).

---

### FIX-16 — Private SDK + Perplexity Deep Research Template Layer
**Origin:** User's idea — session 2026-03-27
**Gate:** 10 real projects completed. Do not attempt before.

**The Problem it solves:**
For niche complex domains (crypto, quant, finance), DeepSeek invents 40-file projects
from scratch. 4,000 lines of WebSocket + order execution logic = high hallucination surface.
FIX-3b local templates cover generic projects (FastAPI, bots, CLI).
This covers niche complex domains where core logic is stable, battle-tested, and repeatable.

**How it works:**
```
Step 1 — Perplexity deep research (done by user, not Agent-XYZ):
  Query: "best open-source Python [domain] libraries — most starred, actively maintained, MIT"
  Perplexity returns: top 3-5 repos with rationale
  User picks one. User reviews license. User audits code quality.

Step 2 — Package wrapping (done by user):
  Clone repo → rip out core logic → wrap with clean interface
  Publish as private pip package: agentxyz-crypto-core, agentxyz-quant-core, etc.
  Host on GitHub Packages (free private PyPI registry)
  User writes tests for the wrapper. Package is immutable after publish.

Step 3 — .pyi stub generation (automated):
  python -c "import mypackage; ..." → extract all public signatures
  Write to templates/stubs/agentxyz_crypto_core.pyi
  These stubs are what Agent-XYZ receives — never the source code

Step 4 — Agent-XYZ build (zero hallucination on core logic):
  Task 1: write requirements.txt → includes --extra-index-url + package name
  Task 2: write main.py → imports from agentxyz_crypto_core → 20 lines of glue
  FIX-2 (pip install): installs package before pytest → zero VPS RAM cost
  pytest: only tests glue code → tiny surface area
  Agent-X cannot edit the package → hallucination on core logic = physically impossible
```

**Why Perplexity deep research specifically:**
Standard Google search returns SEO noise. Perplexity deep research:
- Reads GitHub READMEs + issues + commit history
- Surfaces maintenance status (last commit, open issues, PR velocity)
- Compares multiple candidates with rationale
- Gives the right context to make a safe packaging decision
One Perplexity query per domain = better than 2 hours of manual research.

**Domain target list (build these packages when gate is met):**
```
agentxyz-crypto-core     → Binance/ccxt WebSocket + order execution
agentxyz-quant-core      → pandas + ta-lib strategy patterns
agentxyz-polymarket-core → prediction market odds + position management
agentxyz-telegram-core   → python-telegram-bot wrapper (already thin — low priority)
```

**VPS compatibility:** GitHub Packages install via uv pip = zero RAM. FIX-2 already handles it.

**What maps to existing code (no new build before gate):**
- .pyi stub injection → FIX-1 (AST mapper) extended to handle external stubs
- pip install from GitHub Packages → FIX-2 (requirements.txt install already works)
- Template match → FIX-3b manifest.yaml gets `sdk_package` field when available

**Size (when gate met):** ~30 lines orchestrator + manifest.yaml extension + stub files per domain.
**Not a code change until 10 real projects prove which domains repeat.**

---

### FIX-17 — Dynamic Test Generation
**Origin:** 2026-03-28 session — Devin comparison, dynamic tests per language + project type
**Gate:** After FIX-3 (scaffold) is working. conftest.py is part of scaffold — needs T0 to exist first.

**What is broken:**
Agent-X writes tests but has no knowledge of which testing framework to use or what
patterns are correct for the project type. A FastAPI project needs TestClient, not raw
function calls. A CLI tool needs subprocess.run, not HTTP calls. A Telegram bot needs
MockBot handler testing. Without framework guidance, Agent-X invents patterns — wrong
imports, wrong fixtures, wrong assertion style. Tests fail at import time before any
logic is checked.

AcceptanceCriteria has the right I/O cases (what to test). The gap is HOW to write
those tests for the correct framework and language.

**What changes — four parts:**

Part 1 — TEST_FRAMEWORK_MAP (phase3/test_framework.py, ~30 lines):
```python
TEST_FRAMEWORK_MAP = {
    "python": {
        "web_api":  "pytest + httpx.TestClient",
        "cli":      "pytest + subprocess.run",
        "bot":      "pytest + unittest.mock",
        "data":     "pytest + pandas DataFrame assertions",
        "default":  "pytest"
    },
    "nodejs": {
        "web_api":  "jest + supertest",
        "cli":      "jest + child_process",
        "bot":      "jest + telegraf mock",
        "default":  "jest"
    },
    "go": {
        "web_api":  "testing.T + httptest.NewRecorder",
        "cli":      "testing.T + os/exec",
        "default":  "testing.T + table-driven"
    },
    "typescript": {
        "web_api":  "jest + supertest + ts-jest",
        "default":  "jest + ts-jest"
    }
}

TEST_EXAMPLE_MAP = {
    "python/web_api": "def test_create(client):\n    r = client.post('/todos', json={'title': 'x'})\n    assert r.status_code == 201\n    assert r.json()['title'] == 'x'",
    "python/cli":     "def test_add():\n    r = subprocess.run(['python', 'main.py', 'add', 'x'], capture_output=True)\n    assert r.returncode == 0\n    assert 'x' in r.stdout.decode()",
    "nodejs/web_api": "it('POST /todos', async () => {\n    const r = await request(app).post('/todos').send({title: 'x'})\n    expect(r.status).toBe(201)\n    expect(r.body.title).toBe('x')\n})",
    "go/web_api":     "func TestCreate(t *testing.T) {\n    w := httptest.NewRecorder()\n    r := httptest.NewRequest('POST', '/todos', body)\n    router.ServeHTTP(w, r)\n    assert.Equal(t, 201, w.Code)\n}"
}
```
Key: `language + "/" + project_type`. Falls back to `language/default` if no exact match.

Part 2 — conftest.py in Scaffold (FIX-3 extension, ~20 lines per project_type):
T0 scaffold generates conftest.py / jest.config.js / testmain_test.go based on
project_type + language detected from brief.yaml goal:
```
python/web_api  → conftest.py: TestClient fixture + in-memory SQLite fixture
python/bot      → conftest.py: MockBot fixture + patch decorators
nodejs/web_api  → jest.config.js + beforeAll DB setup
go/web_api      → testmain_test.go with setup/teardown
```
Fixtures exist before any implementation task runs. No fixture import errors possible.

Part 3 — Agent-Y AcceptanceCriteria becomes framework-precise:
test_framework string injected into CREATION_SYSTEM_PROMPT context so Agent-Y
generates I/O cases with correct assertion style:
```
Without FIX-17: "create todo works"
With FIX-17:    "POST /todos returns 201, body.title == input — use TestClient fixture"
```
Agent-Y prompt addition: ~5 lines injecting `test_framework` from TEST_FRAMEWORK_MAP.

Part 4 — Agent-X prompt gets test example injected (FIX-1 mechanism):
TEST_EXAMPLE_MAP lookup injected into _build_agent_x_prompt() alongside global_interfaces.
Agent-X sees exactly what the test pattern should look like for this language + project_type.
Zero new infrastructure — same injection point as FIX-1.

**Detection (zero API cost):**
project_type already detected by Telegram spec menu keyword matching.
language already in SharedState from FIX-14.
TEST_FRAMEWORK_MAP lookup = dict access, O(1).

**What this unlocks:**
```
FastAPI project   → pytest + TestClient + SQLite fixture auto-generated
Telegram bot      → pytest + MockBot handler tests
CLI tool (Python) → pytest + subprocess.run pattern
Express API       → jest + supertest endpoint tests
Go REST API       → table-driven tests + httptest recorder
```
Tests are correct on first attempt. No framework import errors. No wrong assertion style.
Retry rate on test tasks drops significantly.

**Size:** ~80 lines total. No new infrastructure. One new file (test_framework.py) + scaffold extension + 2 prompt injections.
**Done condition:** pytest passes + test that correct framework string is selected for 4 project_type + language combos.

---

### FIX-18 — Agentic RAG for Creation Mode (Creation Context Builder)
**Origin:** 2026-03-28 session — phase2 context_builder already does agentic RAG (reads files +
fetches GitHub + BM25 retrieval + web fallback). Phase3 orchestrator never calls it. Agent-X
retries blindly while the intelligence sits unused in phase2.
**Gate:** After FIX-9 (stable Agent-X, placeholder detection working).

**What is broken:**
phase2/context_builder.py already does exactly what we need:
  Section 1 — error summary (category, keyword, affected file, bug signature)
  Section 2 — reads the actual broken file content. Falls back to GitHub API if missing.
  Section 3 — BM25 + TF-IDF + Thompson hybrid RAG → top 3 past fixes tagged HIGH/LOW
  Web fallback — when RAG empty AND DependencyError/EnvironmentError → fetches Stack Overflow live

phase3/orchestrator.py never calls any of this. On retry:
  Agent-X gets: "tests failed, try again" — no file content, no RAG, no diagnosis.
  It guesses. Complex bugs (circular imports, wrong module path, schema mismatch) hit 3 retries
  and give up — not because the fix is hard, but because Agent-X never saw the broken file.

**Why NOT a new diagnostics.py:**
The original spec proposed building diagnostics.py from scratch (~40 lines):
  extract_file_from_traceback() — regex on tracebacks
  read_file_safe() — pathlib read
  grep_codebase() — subprocess ripgrep
  classify_root_cause() — rule-based error classifier

context_builder.py already does all of this and more. Rebuilding it is duplication.
The real fix is a 30-line adapter that plugs phase3 into the existing agentic RAG.

**What changes — new file + schema extension:**

Part 1 — phase3/creation_context_builder.py (NEW, ~30 lines):
Adapts context_builder.build_context() to creation mode inputs.

read::        cannot open `read:' (No such file or directory)
fixture_path: cannot open `fixture_path' (No such file or directory)
/:            directory
file:         cannot open `file' (No such file or directory)
File:         cannot open `File' (No such file or directory)
read::        cannot open `read:' (No such file or directory)
repo_path:    cannot open `repo_path' (No such file or directory)
/:            directory
failing_file: cannot open `failing_file' (No such file or directory)



Wired into orchestrator.py retry path:


Only fires on retry — first attempt stays lean. Diagnosis adds context only when the
first attempt already proved it was needed.

**Error type routing:**


Part 2 — Reasoning Trace in memory.jsonl (memory/memory_store.py, ~20 lines):
Unchanged from original spec. Add three optional fields to MemoryEntry:

Written in the existing finally: block when diagnosis ran. Omitted when skipped.
These fields ARE the <think> block for LoRA training — earned from real execution.

**What automatically improves when FIX-10 ships:**
FIX-10 adds BM25F field weighting to MemoryEngine._score_entries().
Both phase2/context_builder and phase3/creation_context_builder call find_for_rag().
FIX-10 improves RAG precision in both pipelines simultaneously. Zero extra work.

**What this unlocks:**


**Size:** ~30 lines total (down from 60). New file: phase3/creation_context_builder.py (~30 lines).
Schema extension: ~20 lines in memory_store.py. No diagnostics.py needed.
**Done condition:** pytest passes + test that ImportError retry injects file content + RAG results
into prompt, memory entry written with diagnosis_steps >= 2 entries and root_cause non-empty.nalysis
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
  FIX-1: L2/L9  _run_ast_mapper scope + global_interfaces injection + SkillVault wiring (~15 lines)
  FIX-2: L3+G   pip install + Surgical Pytest (-x --ff + timeout tiers) (~15 lines)
  FIX-3: A1     no scaffold task T0 — blank directory start     (30 lines)

TIER 2 — Breaks mid-complexity projects
  FIX-4: L7     no requirements.txt generation in plan          (prompt change)
  FIX-5: A3     plan_goal() ignores context.md on resume        (10 lines)
  FIX-6: L10    replan() never fires + empty failed_diff when it does  (~13 lines)

TIER 3 — Breaks advanced features
  FIX-7: A5     file_edit sends raw text not unified diff       (30 lines)
  FIX-8: B4     resolve_safe_path() missing on some writes      (audit)
  FIX-9: L5     placeholder code not detected before pytest     (15 lines)

TIER 4 — Unlocks Devin-like test quality + diagnostic reasoning (gated: after FIX-3/FIX-9)
  FIX-17: dynamic test generation — TEST_FRAMEWORK_MAP + conftest.py per project_type (~80 lines)
  FIX-18: agentic RAG for creation mode — creation_context_builder.py adapts existing context_builder (~30 lines)

REJECTED — do not build
  Async API calls  violates VPS sequential constraint (1 vCPU)
  Line limit 300   defeats task decomposition discipline
  Obsidian brain   visualization, not critical path — v4.2
```

---

## TIER 1 — DETAILED ANALYSIS

---

### FIX-1 — global_interfaces never injected + _run_ast_mapper wrong scope + SkillVault disconnected
**Files:** phase3/orchestrator.py → _build_agent_x_prompt() + _run_ast_mapper()
**Source:** Runnable L2 + L9 + 2026-03-28 audit

**What is broken — 3 connected gaps in the same function chain:**

Gap A — _run_ast_mapper() maps wrong scope:
_run_ast_mapper() calls map_repo(fp.parent) — maps the ENTIRE parent directory, not just the file.
If task touches models.py and routes.py (same dir): full directory skeleton stored twice under
two different keys. By task 8, global_interfaces contains duplicate bloated data.
Fix: call _extract_signatures() directly on the specific file, not map_repo() on its parent.

Gap B — global_interfaces never injected into prompt:
After Gap A is fixed, global_interfaces has correct per-file signatures.
But _build_agent_x_prompt() never reads state.global_interfaces.
Agent-X writes every task with zero knowledge of what previous tasks built.
Fix: format global_interfaces as a text block, append to prompt.

Example failure without FIX-1:
- Task 1 writes models.py → class User(Base), class Todo(Base)
- Task 2 writes routes.py → guesses wrong import path for User
- pytest: ImportError — even though models.py exists and is correct

Gap C — SkillVault initialized but never used:
orchestrator.py creates SkillVault() and sets used_skill_ids = [] but nothing appends to it.
vault.get_context_block(goal) is never called — zero reusable patterns reach Agent-X.
Fix: call vault.get_context_block(task.description) in _build_agent_x_prompt(),
inject result as a Skills section. If vault empty (first run): nothing added, zero cost.

**What changes — ~15 lines, orchestrator.py only:**

Part 1 — fix _run_ast_mapper() (~5 lines):
Replace map_repo(fp.parent) with direct per-file signature extraction.
Result: global_interfaces = {"models.py": ["class User(Base)", "class Todo(Base)"], ...}

Part 2 — inject global_interfaces into _build_agent_x_prompt() (~5 lines):
If global_interfaces non-empty: format as "## What exists so far" block → append to prompt.
If empty (Task 1): skip — zero cost, no empty section injected.

Part 3 — wire SkillVault.get_context_block() into _build_agent_x_prompt() (~3 lines):
Call vault.get_context_block(task.description) → if non-empty → append as "## Reusable patterns".
SkillVault already exists, already works, already has BM25 search. Just not called.

NOTE — RUN_TESTS dead enum:
TaskAction.RUN_TESTS exists in schemas.py but Agent-Y never emits it and orchestrator
never handles it. No action needed. Document as dead value — remove at v4.2 cleanup.

**Impact:** Every Task 2+ goes from triple-blind (no interfaces, no skills, no patterns)
to triple-informed. Biggest ROI of all fixes. Size grows 5 → ~15 lines, still Tier 1.

---

### FIX-2 — pip install missing before pytest + Surgical Pytest (merged FIX-19)
**Files:** phase3/orchestrator.py → _run_tests()
**Source:** Runnable L3 + Gemini 2026-03-28

**What is broken (Part 1 — install):**
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

**What is broken (Part 2 — Surgical Pytest):**
_run_tests() already targets the task's test file when one is in files_to_touch.
But it is missing three things:
1. `-x` (fail fast): pytest runs all failures even when the first is enough — wastes time + floods logs
2. `--ff` (failed first): on retry, pytest does not prioritise the test that just failed
3. Full suite gate: tasks with no test file fall back to `pytest .` (full repo) — wrong trigger point

Without these: a 3-retry bug on a project with 40 tests takes minutes per retry instead of seconds.
The feedback loop collapses on any real project.

**NOTE — existing code already does file-level targeting:**
```python
# orchestrator.py:343 — already exists, not broken, just incomplete
test_files = [f for f in task.files_to_touch if f.startswith("test_")]
if test_files:
    pytest_target = str(repo_path / test_files[0])  # ← file-level, correct
else:
    pytest_target = str(repo_path)  # ← falls back to full repo — fix this
```

**What changes — _run_tests() only, ~15 lines total:**

```python
def _run_tests(repo_path: Path, task: Task) -> bool:
    import os
    # Part 1 — install dependencies before running any tests
    req = repo_path / "requirements.txt"
    if req.exists():
        installer = "uv" if _uv_available() else "pip"
        cmd = [installer, "pip", "install", "-r", str(req)] if installer == "uv" \
              else [sys.executable, "-m", "pip", "install", "-r", str(req)]
        subprocess.run(cmd, cwd=repo_path, capture_output=True, check=False)

    # Part 2 — Surgical Pytest: 3-tier targeting
    test_files = [f for f in task.files_to_touch if f.startswith("test_")]
    if test_files:
        # Tier 1 — micro-loop: file-level, fail fast, failed first
        target = str(repo_path / test_files[0])
        timeout = int(os.environ.get("TEST_TIMEOUT_FILE", "30"))
        cmd = [sys.executable, "-m", "pytest", target, "-x", "--ff", "--tb=short", "-q"]
    else:
        # No test file in this task (scaffold, requirements.txt, config)
        # Skip pytest — next task's test will catch issues
        # Full suite runs only at iteration audit (FIX-13 trigger)
        return True

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        log.warning("orchestrator.test_failed",
                    stdout=result.stdout[-600:], stderr=result.stderr[-200:])
    return result.returncode == 0
```

**.env.example additions:**
```
TEST_TIMEOUT_FILE=30      # seconds per file-level test run (retries stay fast)
TEST_TIMEOUT_FULL=600     # seconds for full suite at iteration audit (FIX-13)
```

**3-tier structure — how it maps to the full architecture:**
```
Tier 1 — Micro-loop (this fix):
  file-level targeting + -x --ff → retries take seconds not minutes
  already implemented for targeting; adding fail-fast flags only

Tier 2 — Domain merge (FIX-15):
  after domain completes → run pytest tests/domain_a/ before moving to Domain B
  FIX-15 already plans this; _run_tests() timeout = TEST_TIMEOUT_FILE × domain_size

Tier 3 — Full suite release (FIX-13):
  after ALL tasks complete → iteration audit triggers pytest . with TEST_TIMEOUT_FULL
  only time the full suite runs — not during retries, not between tasks
```

**Why NOT pytest-xdist (parallel):**
2GB VPS. Parallel workers + database fixtures = OOM crash. Sequential only. Locked.

**Constraint locked by VPS rules:**
Use uv for all dependency management. No per-project venv. Global cache only.

**Pre-build risk audit (2026-03-28):**
Current _run_tests() state vs spec — exact collision map:

| Item | Current | Action |
|------|---------|--------|
| test_files targeting | EXISTS (line 374) | keep — do not rewrite |
| -q --tb=short flags | EXISTS | keep |
| -x --ff flags | MISSING | add to cmd |
| timeout=60 hardcoded | WRONG — spec uses TEST_TIMEOUT_FILE env var | replace |
| else: pytest_target = str(repo_path) | WRONG — spec says return True | replace |
| try/except wrapper | EXISTS — spec omits it but it is correct | keep |
| pip install block | MISSING entirely | add above pytest logic |
| _uv_available() helper | MISSING — only in spec | add above _run_tests() |
| .env.example timeout vars | MISSING | add after code |

Exact edit plan (3 edits, one file + one config):
1. Add _uv_available() helper directly above _run_tests()
2. Replace _run_tests() body — keep try/except shell, replace everything inside
3. Add TEST_TIMEOUT_FILE=30 and TEST_TIMEOUT_FULL=600 to .env.example

Spec code block is correct as-is — paste inside existing try/except, do not strip it.

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

### FIX-6 — replan() never fires + fires with empty context when it does
**Files:** phase3/orchestrator.py → run_loop() + run_once() failure path
**Source:** Runnable L10 + 2026-03-28 audit

**What is broken — 2 layers:**

Layer A — replan() is never triggered (the real bug):
When failed_task_streak hits 2, run_once() does this:
  log.info("orchestrator.streak_2 — Agent-Y replan needed")  ← just a log message
  state = mark_failed(state, task.task_id, "streak_limit")
  return state                                              ← returns, replan never called

run_loop() only calls plan_goal() when plan is EMPTY. After streak==2, plan is NOT empty
(there are still pending tasks). So plan_goal() is never triggered either.

Result: streak hits 2 → task marked failed → run_once() returns → run_loop() calls
run_once() again → next pending task ALSO immediately hits streak==2 check → also
marked failed without running → all remaining tasks cascade-fail. Build dies silently.

Layer B — when replan fires, failed_diff is empty:
replan() accepts failed_diff: str — what Agent-X last wrote that failed.
Even after fixing Layer A, the orchestrator captures no failed content to pass.
Agent-Y replans blind → same plan → same failure → true infinite loop.

This is the most dangerous gap: it LOOKS like replan fires (log says so) but nothing
actually happens. The build silently dies or loops forever.

**What changes — 2 parts:**

Part 1 — add replan trigger to run_loop() (~8 lines):
After run_once() returns, check if failed_task_streak == 2.
If yes: call replan() with last_failed_content → replace remaining plan tasks.
Reset failed_task_streak to 0 after replan so new sub-tasks get fresh attempts.
Max replan count = 2 (already locked in hard rules).

Part 2 — capture failed content in run_once() (~5 lines):
_execute_file_ops(): capture last DeepSeek output even on failure.
Surface it back through run_once() return value or state field.
run_loop() passes it to replan() in Part 1.

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

**What changes — three gates before write_file():**
```
Gate 1 — Placeholder check (original FIX-9):
  _is_placeholder(content): regex catches TODO/pass stubs
  If placeholder → reject immediately, retry with correct reason

Gate 2 — Syntax check (expanded from REVIEW 6):
  ast.parse(content): catches syntax errors before pytest boots
  If SyntaxError → reject, retry with "your code has a syntax error"
  Zero RAM, zero API cost, faster than pytest

Gate 3 — Import validation (expanded from REVIEW 6):
  if task_number > 1 and global_interfaces not empty:
    check all import statements against global_interfaces
    if import not found → reject, retry with "X does not exist yet"
  SKIP on task 1 (global_interfaces empty — nothing to validate against)
```

All three gates run before write_file(). If any fails → reject + correct retry reason.
Pytest remains gate 4 — logic correctness, unchanged.

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

---

---

### FIX-3b — Template Scaffold Library (enhances FIX-3)

**Files:**
- templates/fastapi_crud/         NEW — proven FastAPI CRUD structure
- templates/telegram_bot/         NEW — proven Telegram bot structure
- templates/cli_tool/             NEW — proven CLI tool structure
- templates/manifest.yaml         NEW — template index + tags
- phase3/orchestrator.py          MOD — match_template() called before scaffold
- phase3/plan_checkpoint.py       MOD — show template match in plan display

**What is broken:**
FIX-3 scaffold creates stub files (pass-only bodies, correct structure).
Agent-X still generates all boilerplate from scratch: main.py setup, database.py,
requirements.txt, conftest.py. DeepSeek invents these every time.
Result: wrong imports, wrong patterns, structural retries on code that never changes
project to project.

**What changes:**
Before scaffold runs, attempt template match on goal string.
Match found: copy template files as base → Agent-X only generates custom logic.
No match: fall back to FIX-3 stub approach (unchanged).

Template match is keyword-based, zero API calls, zero cost.
Minimum 2 tag matches required before template is used.
User always sees plan at Plan Checkpoint — template match shown as:
"Matched FastAPI CRUD template. Only generating your custom logic."

**Templates organized by NICHE (domain-first, not tech-first):**
```
crypto/
  price_feed       tags: crypto, price, feed, websocket, ccxt, binance
  trading_bot      tags: crypto, trading, strategy, order, exchange, bot
  portfolio        tags: crypto, portfolio, pnl, multi-exchange, tracker

stocks/
  screener         tags: stocks, equity, screener, yfinance, signal, alert
  backtester       tags: stocks, backtest, pandas, ta-lib, strategy

polymarket/
  market_bot       tags: polymarket, prediction, odds, market, bet, position

web/
  fastapi_crud     tags: fastapi, crud, rest, api, endpoint, sqlalchemy
  dashboard        tags: dashboard, streamlit, charts, live, data, ui

bots/
  telegram_bot     tags: telegram, bot, message, command, handler
  discord_bot      tags: discord, bot, slash, command, embed

data/
  pipeline         tags: pipeline, etl, scraper, data, csv, transform
```

RAG fallback when no template matches:
  BM25 queries memory.jsonl with goal keywords + failure_category
  Top 3 accepted patterns injected into Agent-Y prompt as context
  Agent-Y generates informed plan instead of blank canvas
  Plan shown at Plan Checkpoint — user always confirms

Templates use {{placeholder}} for custom parts only:
  {{model_name}}, {{command_name}}, {{project_name}}
Everything else is proven boilerplate — never generated by DeepSeek.

**Fallback (always safe):**
No template match → FIX-3 stub approach → Plan Checkpoint asks user:
"No template for this project type. Here's my plan — does this look right?"

**Impact:**
~40% fewer DeepSeek calls per project (boilerplate files pre-filled).
Structural errors (wrong imports, wrong paths) on common project types: gone.
Covers 80% of real project requests with 3 templates.

**Build gate:** after FIX-3 is working and tested.
**Size:** ~50 lines new code + 3 template directories.

---

## LOOP CONTROL LAYER — FIX-11 + FIX-12 (after FIX-9)

These two fixes form one coherent system: user control over the build loop.
FIX-11 = control BEFORE build. FIX-12 = control DURING build.
Build FIX-11 first. FIX-12 depends on interrupt_queue structure from FIX-11.

---

### FIX-11 — Plan Checkpoint + User Type UX

**Files:**
- phase3/orchestrator.py        → add plan checkpoint at start of run_loop()
- agent_y/reasoner.py           → add interpret_plan_for_user()
- phase3/telegram_bot.py        → plan display + inline buttons + timer
- phase3/schemas.py             → add plan_approved: bool + user_type: str to SharedState
- NEW: phase3/plan_checkpoint.py → format plan, detect user type, timer logic (~40 lines)

**What is broken:**
Agent-Y plans → Orchestrator immediately starts executing. No pause. No user review.
If Agent-Y misunderstood the brief, 30 minutes of API calls are wasted before user sees output.
User has no chance to catch wrong assumptions before building starts.

**What changes:**

plan_checkpoint.py — four functions:
```
detect_user_type(goal: str) → "technical" | "general"
  technical keywords (FastAPI, SQLAlchemy, endpoint, pytest) → technical
  plain language → general

format_plan_technical(plan) → str
  T1: models.py — User, Todo (SQLAlchemy)
  T2: routes.py — CRUD endpoints
  [✅ Build] [✏️ Change] — 10 min timer

format_plan_general(plan) → str
  ✅ Core (always built): Todo list, save to database
  🔵 Optional (your choice): User login (recommended), Email reminders
  No reply in 10 mins → building core + recommended, skipping rest
  [✅ All] [🔵 Core + recommended] [⚡ Core only]

run_checkpoint(plan, state) → bool
  send formatted plan to Telegram
  wait PLAN_APPROVAL_TIMEOUT seconds (default 600 — configurable in .env)
  ✅ approve   → return True
  ✏️ change    → call replan() with user instruction → show plan again (loop max 3)
  no response  → mark task.required=False tasks as SKIPPED → return True
```

orchestrator.py — one addition to run_loop():
```python
# after plan_goal(), before first task:
approved = run_checkpoint(state.plan, state)
# approved is always True (timeout also returns True with skips applied)
```

Timer defaults:
```
task.required = True  → always built, timer has no effect
task.required = False → timeout → SKIPPED (conservative, always safe)
PLAN_APPROVAL_TIMEOUT = 600  (10 min — add to .env.example)
```

**Size:** ~60 lines total. No logic changes to existing loop.
**Done condition:** pytest passes + Telegram mock shows correct plan format for technical and general briefs.

---

### FIX-12 — Mid-task Interrupt Handler

**Files:**
- phase3/orchestrator.py          → _check_interrupts() called before every task
- phase3/schemas.py               → TaskStatus.SKIPPED + interrupt_queue: list[str] in SharedState
- phase3/telegram_bot.py          → pipe all incoming messages → state.interrupt_queue
- NEW: phase3/interrupt_handler.py → intent parser + cascade skip (~40 lines)

**What is broken:**
Every AI coding agent today (Claude Code, Codex, OpenClaw) ignores mid-task user messages.
Message arrives while agent is executing → queued → read only after current action completes → too late.
User says "skip auth, it already exists" → auth gets built anyway.
Root cause: no task boundaries. One big execution block. No interrupt window.

Agent-XYZ has task boundaries by design (50-line atomic tasks).
The gap between tasks is a natural, free interrupt window. It is not being used.

**What changes:**

interrupt_handler.py — three functions:
```
parse_intent(message: str) → dict
  "stop"              → {action: STOP}
  "skip X" / "X exists" / "don't build X"  → {action: SKIP, keyword: "X"}
  "change X to Y"     → {action: MODIFY, instruction: "..."}
  anything else       → {action: CONTINUE}

cascade_skip(state, keyword: str) → None
  find all tasks where keyword in description.lower()
  mark them SKIPPED
  find all tasks with depends_on containing any SKIPPED task_id → also SKIPPED
  log: "Skipped T4 (auth), T5 (middleware — depends on T4)"

check_interrupts(state) → dict
  drain state.interrupt_queue (list of pending Telegram messages)
  parse each → return highest priority intent
  priority: STOP > SKIP > MODIFY > CONTINUE
```

orchestrator.py — loop change:
```python
# before every task execution:
intent = check_interrupts(state)
if intent["action"] == "STOP":
    report_halt(state)
    break
elif intent["action"] == "SKIP":
    cascade_skip(state, intent["keyword"])
    continue  # re-evaluate next pending task
elif intent["action"] == "MODIFY":
    surgical_replan(state, intent["instruction"])
# CONTINUE → fall through to normal execution
```

TaskStatus enum addition:
```python
class TaskStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    DONE        = "done"
    FAILED      = "failed"
    BLOCKED     = "blocked"
    SKIPPED     = "skipped"   # ← new
```

Completion report format:
```
Build complete.
✅ Built:   T1 models, T2 routes, T3 tests (3 tasks)
⏭️ Skipped: T4 auth (user request), T5 middleware (depends on T4)
📦 Pushed:  agent-x/fix-abc123
```

**Why this is a moat:**
Other agents: monolithic execution, no task boundaries → cannot interrupt mid-build by design.
Agent-XYZ: atomic 50-line tasks → interrupt window exists between every task → free.
This is an architectural advantage, not a feature bolt-on.

**Size:** ~70 lines total.
**Done condition:** pytest passes + test that SKIP message cascades correctly to dependent tasks.

**Git milestone checkpoint (added from REVIEW 6):**
After iteration audit passes → git tag milestone-{n}
If next iteration fails catastrophically → git reset --hard milestone-{n}
Zero new infrastructure. Blast radius fully contained per milestone.

---

---

### FIX-14 — Multi-language Backend Support

**Files:**
- phase3/schemas.py              → add language: str = "python" to SharedState
- phase3/orchestrator.py         → _run_tests() + FIX-2 installer become language-aware
- phase3/plan_checkpoint.py      → warn user if Tier 2/3 language selected
- templates/manifest.yaml        → add language tag to each template

**What is missing:**
brief.yaml has no language field. Agent-Y always assumes Python.
_run_tests() in creation mode calls pytest directly — not wired to multi-language executor.
FIX-2 (install deps) assumes requirements.txt + uv pip install — Python only.
Multi-language executor EXISTS from v2.1.6 but is not connected to creation mode pipeline.

**Why this is NOT an architectural fork:**
Exit code is the universal truth signal: 0 = green, non-zero = red.
pytest, jest, go test all return exit code. Thompson Sampling + Best-of-N read exit code only.
Zero changes needed to Thompson, Best-of-N, DecisionEngine — they are already language-agnostic.
The entire "fork" is a dict lookup in _run_tests() and a language-aware FIX-2.

**What changes:**

FIX-2 becomes language-aware (same fix, wider scope):
```
python     → uv pip install -r requirements.txt
nodejs     → npm install
go         → go mod tidy
typescript → npm install
```

_run_tests() dynamic router (wires existing multi-language executor):
```
python     → pytest --json-report
nodejs     → npm test
go         → go test ./...
typescript → npm test
```

Agent-X prompt gets language injected (FIX-1 mechanism, same approach):
  Python → writes def test_foo(): assert ...
  Node.js → writes it('should...', () => { expect(...).toBe(...) })
  AcceptanceCriteria schema unchanged — I/O cases are language-agnostic strings.

Plan Checkpoint warns on Tier 2, redirects on Tier 3/4.

**Language tiers (locked):**
```
Tier 1 (build now):       python, nodejs
Tier 2 (warn + proceed):  go, typescript
Tier 3 (warn + redirect): rust, ruby, php, java, csharp
```

**Size:** ~20 lines total. Dict lookup + language field in schema + prompt injection.
**Gate:** after FIX-3b template library exists (needs template language tags).

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

---

---

### FIX-15 — Domain Splintering (Topological Sort Architecture)
**Origin:** User's idea — session 2026-03-27 (explored via Merge Sort + Quick Sort → resolved to Topological Sort)
**Gate:** After FIX-9 is done and passing. Do not attempt before.

**The Problem it solves:**
Linear orchestration (Task1→Task2→...→Task40) compounds failure probability.
At 90% per-task success: 0.90^40 = 1.5% end-to-end success on 25-file projects.
Domain Splintering resets the compound probability per domain, not per project.

**Why Topological Sort (not Merge Sort or Quick Sort):**
```
Merge Sort alone:   splits into equal chunks (5-6 files) — predictable size
                    BUT ignores dependency order — Domain B might need a file
                    that ended up in Domain C by accident

Quick Sort alone:   pivot = most-imported file, build it first
                    BUT chunk sizes vary wildly (2 files vs 15 files)
                    AND Agent-Y must predict the pivot before files exist

Topological Sort:   the parent algorithm both are approximating
                    Step 1 — Agent-Y predicts full dependency graph from brief
                              (FastAPI: models.py has most imports pointing to it)
                    Step 2 — Topological sort determines BUILD ORDER of all files
                              (most-depended-upon file always built first)
                    Step 3 — Slice into equal chunks of 5-6 files (Merge Sort sizing)
                              preserving topological order within each chunk
                    Step 4 — Each chunk = one domain, built in dependency order

Result: domain SIZE is bounded (Merge Sort) + domain ORDER is dependency-correct
        (Quick Sort pivot) + no accidental cross-domain import failures
```

**Viva sentence:** "Agent-Y runs topological sort on the dependency DAG predicted
from the brief, then slices into equal domains. Domain order = dependency order.
Domain size = bounded complexity. DeepSeek never sees more than 6 files at once."

**How it works:**
```
Plan phase (two-stage Agent-Y — same model, two sequential calls):
  Call 1: brief → full file list + predicted dependency edges
  Call 2: file list + edges → topological sort → slice into domains of 5-6 files
           output: domains[] with build order + dependency graph

  Example (FastAPI CRUD, 20 files):
    Domain A: config.py, database.py, models.py    (no deps — foundation)
    Domain B: schemas.py, crud.py, auth.py         (depends on A signatures)
    Domain C: routes.py, middleware.py, deps.py    (depends on A+B signatures)
    Domain D: main.py, tests/, requirements.txt    (imports all — glue)

Build phase: each domain = isolated mini-project
  Domain A: build → 4-gate check → pytest → extract AST signatures → ✅
  Context boundary (free — just control global_interfaces contents)
  Domain B: receives only Domain A .pyi signatures → build → pytest → ✅
  Context boundary
  Domain C: receives Domain A+B signatures only → build → pytest → ✅
  Context boundary
  Domain D: receives all signatures → integration test → ✅
```

**Math improvement:**
```
Old (linear):  0.90^40 = 1.5%   end-to-end
New (domains): 0.90^6  = 53%    per domain × human checkpoint between domains
```

**What changes:**
- SharedState gets `domains: list[Domain]` alongside `plan: list[Task]`
- Agent-Y CREATION_SYSTEM_PROMPT: two-stage planning (file list → domain split)
- Orchestrator: outer domain loop wraps existing task loop — inner loop UNCHANGED
- Human checkpoint (FIX-11) shown between every domain, not just at start
- No new agent needed — two-stage Agent-Y is same model, two API calls

**Context boundary — it's free, not a new mechanism:**
Agent-X is stateless — every DeepSeek API call is already a fresh context window.
"Context wipe" = just control what global_interfaces contains at domain boundaries.
Domain B receives only Domain A's AST signatures, never Domain A's full source files.
FIX-1 already controls this. Zero new code needed for context isolation.

**Backward compatibility — zero regression:**
Simple project (<10 files) → Agent-Y emits 1 domain → outer loop runs once
→ behavior identical to today's linear loop → no existing tests break.

**Cons — properly specced:**

Con 1: Circular dependency deadlock
  Problem: Agent-Y predicts bad dependency graph — Domain B depends on C, C on B.
           Topological sort fails. Build never starts. No error raised.
  Fix: DAG validation at Plan Checkpoint (FIX-11), BEFORE first domain build:
    ```python
    def validate_domain_dag(domains: list[Domain]) -> bool:
        # DFS cycle detection on domain dependency graph
        # if cycle found → return False
    # cycle detected → reject plan
    # Telegram: "Circular dependency between Domain B and C — replanning"
    # ask Agent-Y to replan domain split → max 2 replans → then human redesigns
    ```
  Size: ~15 lines DFS. Runs at Plan Checkpoint only.

Con 2: Integration failure (semantic vs syntax mismatch)
  Problem: Domain A builds save_trade(price: float). Domain D calls save_trade(trade_data: dict).
           Both pass isolated pytest. Integration test fails. Which domain is wrong?
           Auto-editing either domain risks breaking its own isolated tests.
  Fix: Structured failure flow using FIX-12 interrupt mechanism:
    ```
    Integration test fails →
      Telegram: "Integration failed.
                 Error: save_trade() expected float, got dict.
                 Domain A owns it. Domain D calls it.
                 Which domain to fix? Reply: A / B / C / D"
      Orchestrator pauses (FIX-12 already has pause/resume)
      User replies "A" →
      Orchestrator reopens Domain A tasks from the broken interface
      Domain A rebuilt → AST re-extracted → retry integration test
      Max 2 integration retries → human takeover, orchestrator halts
    ```
  Rule: orchestrator NEVER auto-edits a completed domain without user instruction.
  FIX-12 interrupt handler already has the pause/resume mechanism — just wire it here.

**Prerequisite:** ast_mapper.py already exists (phase2/tools/ast_mapper.py). FIX-1 must be done first — it fixes _run_ast_mapper() scope and injects global_interfaces. Without FIX-1, domain signatures cannot be passed between domains correctly.
**Size:** ~75 lines total — outer domain loop (~30) + DAG validation (~15) + integration failure flow (~30 wired to FIX-12).

---

### FIX-16 — Private SDK + Perplexity Deep Research Template Layer
**Origin:** User's idea — session 2026-03-27
**Gate:** 10 real projects completed. Do not attempt before.

**The Problem it solves:**
For niche complex domains (crypto, quant, finance), DeepSeek invents 40-file projects
from scratch. 4,000 lines of WebSocket + order execution logic = high hallucination surface.
FIX-3b local templates cover generic projects (FastAPI, bots, CLI).
This covers niche complex domains where core logic is stable, battle-tested, and repeatable.

**How it works:**
```
Step 1 — Perplexity deep research (done by user, not Agent-XYZ):
  Query: "best open-source Python [domain] libraries — most starred, actively maintained, MIT"
  Perplexity returns: top 3-5 repos with rationale
  User picks one. User reviews license. User audits code quality.

Step 2 — Package wrapping (done by user):
  Clone repo → rip out core logic → wrap with clean interface
  Publish as private pip package: agentxyz-crypto-core, agentxyz-quant-core, etc.
  Host on GitHub Packages (free private PyPI registry)
  User writes tests for the wrapper. Package is immutable after publish.

Step 3 — .pyi stub generation (automated):
  python -c "import mypackage; ..." → extract all public signatures
  Write to templates/stubs/agentxyz_crypto_core.pyi
  These stubs are what Agent-XYZ receives — never the source code

Step 4 — Agent-XYZ build (zero hallucination on core logic):
  Task 1: write requirements.txt → includes --extra-index-url + package name
  Task 2: write main.py → imports from agentxyz_crypto_core → 20 lines of glue
  FIX-2 (pip install): installs package before pytest → zero VPS RAM cost
  pytest: only tests glue code → tiny surface area
  Agent-X cannot edit the package → hallucination on core logic = physically impossible
```

**Why Perplexity deep research specifically:**
Standard Google search returns SEO noise. Perplexity deep research:
- Reads GitHub READMEs + issues + commit history
- Surfaces maintenance status (last commit, open issues, PR velocity)
- Compares multiple candidates with rationale
- Gives the right context to make a safe packaging decision
One Perplexity query per domain = better than 2 hours of manual research.

**Domain target list (build these packages when gate is met):**
```
agentxyz-crypto-core     → Binance/ccxt WebSocket + order execution
agentxyz-quant-core      → pandas + ta-lib strategy patterns
agentxyz-polymarket-core → prediction market odds + position management
agentxyz-telegram-core   → python-telegram-bot wrapper (already thin — low priority)
```

**VPS compatibility:** GitHub Packages install via uv pip = zero RAM. FIX-2 already handles it.

**What maps to existing code (no new build before gate):**
- .pyi stub injection → FIX-1 (AST mapper) extended to handle external stubs
- pip install from GitHub Packages → FIX-2 (requirements.txt install already works)
- Template match → FIX-3b manifest.yaml gets `sdk_package` field when available

**Size (when gate met):** ~30 lines orchestrator + manifest.yaml extension + stub files per domain.
**Not a code change until 10 real projects prove which domains repeat.**

---

### FIX-17 — Dynamic Test Generation
**Origin:** 2026-03-28 session — Devin comparison, dynamic tests per language + project type
**Gate:** After FIX-3 (scaffold) is working. conftest.py is part of scaffold — needs T0 to exist first.

**What is broken:**
Agent-X writes tests but has no knowledge of which testing framework to use or what
patterns are correct for the project type. A FastAPI project needs TestClient, not raw
function calls. A CLI tool needs subprocess.run, not HTTP calls. A Telegram bot needs
MockBot handler testing. Without framework guidance, Agent-X invents patterns — wrong
imports, wrong fixtures, wrong assertion style. Tests fail at import time before any
logic is checked.

AcceptanceCriteria has the right I/O cases (what to test). The gap is HOW to write
those tests for the correct framework and language.

**What changes — four parts:**

Part 1 — TEST_FRAMEWORK_MAP (phase3/test_framework.py, ~30 lines):
```python
TEST_FRAMEWORK_MAP = {
    "python": {
        "web_api":  "pytest + httpx.TestClient",
        "cli":      "pytest + subprocess.run",
        "bot":      "pytest + unittest.mock",
        "data":     "pytest + pandas DataFrame assertions",
        "default":  "pytest"
    },
    "nodejs": {
        "web_api":  "jest + supertest",
        "cli":      "jest + child_process",
        "bot":      "jest + telegraf mock",
        "default":  "jest"
    },
    "go": {
        "web_api":  "testing.T + httptest.NewRecorder",
        "cli":      "testing.T + os/exec",
        "default":  "testing.T + table-driven"
    },
    "typescript": {
        "web_api":  "jest + supertest + ts-jest",
        "default":  "jest + ts-jest"
    }
}

TEST_EXAMPLE_MAP = {
    "python/web_api": "def test_create(client):\n    r = client.post('/todos', json={'title': 'x'})\n    assert r.status_code == 201\n    assert r.json()['title'] == 'x'",
    "python/cli":     "def test_add():\n    r = subprocess.run(['python', 'main.py', 'add', 'x'], capture_output=True)\n    assert r.returncode == 0\n    assert 'x' in r.stdout.decode()",
    "nodejs/web_api": "it('POST /todos', async () => {\n    const r = await request(app).post('/todos').send({title: 'x'})\n    expect(r.status).toBe(201)\n    expect(r.body.title).toBe('x')\n})",
    "go/web_api":     "func TestCreate(t *testing.T) {\n    w := httptest.NewRecorder()\n    r := httptest.NewRequest('POST', '/todos', body)\n    router.ServeHTTP(w, r)\n    assert.Equal(t, 201, w.Code)\n}"
}
```
Key: `language + "/" + project_type`. Falls back to `language/default` if no exact match.

Part 2 — conftest.py in Scaffold (FIX-3 extension, ~20 lines per project_type):
T0 scaffold generates conftest.py / jest.config.js / testmain_test.go based on
project_type + language detected from brief.yaml goal:
```
python/web_api  → conftest.py: TestClient fixture + in-memory SQLite fixture
python/bot      → conftest.py: MockBot fixture + patch decorators
nodejs/web_api  → jest.config.js + beforeAll DB setup
go/web_api      → testmain_test.go with setup/teardown
```
Fixtures exist before any implementation task runs. No fixture import errors possible.

Part 3 — Agent-Y AcceptanceCriteria becomes framework-precise:
test_framework string injected into CREATION_SYSTEM_PROMPT context so Agent-Y
generates I/O cases with correct assertion style:
```
Without FIX-17: "create todo works"
With FIX-17:    "POST /todos returns 201, body.title == input — use TestClient fixture"
```
Agent-Y prompt addition: ~5 lines injecting `test_framework` from TEST_FRAMEWORK_MAP.

Part 4 — Agent-X prompt gets test example injected (FIX-1 mechanism):
TEST_EXAMPLE_MAP lookup injected into _build_agent_x_prompt() alongside global_interfaces.
Agent-X sees exactly what the test pattern should look like for this language + project_type.
Zero new infrastructure — same injection point as FIX-1.

**Detection (zero API cost):**
project_type already detected by Telegram spec menu keyword matching.
language already in SharedState from FIX-14.
TEST_FRAMEWORK_MAP lookup = dict access, O(1).

**What this unlocks:**
```
FastAPI project   → pytest + TestClient + SQLite fixture auto-generated
Telegram bot      → pytest + MockBot handler tests
CLI tool (Python) → pytest + subprocess.run pattern
Express API       → jest + supertest endpoint tests
Go REST API       → table-driven tests + httptest recorder
```
Tests are correct on first attempt. No framework import errors. No wrong assertion style.
Retry rate on test tasks drops significantly.

**Size:** ~80 lines total. No new infrastructure. One new file (test_framework.py) + scaffold extension + 2 prompt injections.
**Done condition:** pytest passes + test that correct framework string is selected for 4 project_type + language combos.

---

### FIX-18 — Agentic RAG for Creation Mode (Creation Context Builder)
**Origin:** 2026-03-28 — phase2 context_builder already does agentic RAG (reads files + fetches GitHub + BM25 retrieval + web fallback). Phase3 orchestrator never calls it. Agent-X retries blindly while intelligence sits unused in phase2.
**Gate:** After FIX-9 (stable Agent-X, placeholder detection working).

**What is broken:**
phase2/context_builder.py already does exactly what we need:
  Section 1 — error summary (category, keyword, affected file, bug signature)
  Section 2 — reads the actual broken file content. Falls back to GitHub API if missing.
  Section 3 — BM25 + TF-IDF + Thompson hybrid RAG → top 3 past fixes tagged HIGH/LOW
  Web fallback — when RAG empty AND DependencyError/EnvironmentError → fetches StackOverflow live

phase3/orchestrator.py never calls any of this. On retry:
  Agent-X gets: "tests failed, try again" — no file content, no RAG, no diagnosis.
  It guesses. Complex bugs (circular imports, wrong module path, schema mismatch) hit 3 retries
  and give up — not because the fix is hard, but because Agent-X never saw the broken file.

**Why NOT a new diagnostics.py:**
context_builder.py already does: file read, GitHub fallback, BM25+TF-IDF+Thompson RAG, web fallback.
Rebuilding it in diagnostics.py is duplication. The real fix is a 30-line adapter that plugs
phase3 into the existing agentic RAG. No new tools. No new logic. Just a different input format.

**What changes — new file + schema extension:**

Part 1 — phase3/creation_context_builder.py (NEW, ~30 lines):

Adapts context_builder.build_context() to creation mode inputs:


Wired into orchestrator.py retry path (attempt_idx > 0 only — first attempt stays lean):


Error type routing:


NOTE — _classify_error_type() is NOT a new function:
phase2/classifier/regex_pass.py already classifies error strings into DependencyError,
ImportError, EnvironmentError, etc. creation_context_builder.py calls it directly on
the raw pytest stdout. No new classifier needed — reuse what exists.

Part 2 — Reasoning Trace in memory.jsonl (memory/memory_store.py, ~20 lines):
Add three optional fields to MemoryEntry (written in existing finally: block):

These fields ARE the <think> block for LoRA training — earned from real execution, not synthetic.

**FIX-10 synergy:**
FIX-10 adds BM25F field weighting to MemoryEngine._score_entries().
both phase2/context_builder and phase3/creation_context_builder call find_for_rag().
FIX-10 improves RAG precision in both pipelines simultaneously. Zero extra work.

**What this unlocks:**


**Size:** ~30 lines (down from 60). New file: phase3/creation_context_builder.py (~30 lines).
Schema extension: ~20 lines in memory_store.py. No diagnostics.py needed.
**Done condition:** pytest passes + test that ImportError retry injects file content + RAG results
into prompt, memory entry written with diagnosis_steps >= 2 entries and root_cause non-empty.

---

### FIX-19 — STATE_PATH multi-project isolation (B2)

**Files:**
- `phase3/state_manager.py`    MOD — get_state_path(), write_state(), read_state(), validate_slug()
- `phase3/orchestrator.py`     MOD — ProjectContext class + del ctx after each project

**Source:** Perplexity Sonnet + ChatGPT o4 + Gemini 2.5 Pro research (2026-03-28)

**What is broken:**
STATE_PATH = "memory/state.json" is a hardcoded singleton.
Project B starts → overwrites project A's state mid-build → A is unrecoverable.
Silent corruption. No error raised. Orchestrator continues on wrong state.

**Verdict — state lives OUTSIDE the project repo:**
```
CORRECT:  memory/{slug}/state.json         ← outside workspace
WRONG:    WORKSPACE_ROOT/{slug}/.agent/    ← inside workspace
```

Why outside wins for Agent-XYZ specifically:
- Rollback rule: git reset HEAD -- . → git checkout -- . → git clean -fd
- git clean -fd removes untracked directories
- .agent/ is untracked (gitignored) → git clean -fd DELETES state.json mid-rollback
- Agent-X hallucination risk: shutil.rmtree on workspace kills .agent/ too
- Gemini: "workspace = operating table, memory = surgeon's brain"
- If operating table catches fire → surgeon steps back intact

Hybrid: state = outside. context.md = inside (already committed, v3.1 built).

**What changes:**

```python
# phase3/state_manager.py

import os, json, re, tempfile
from pathlib import Path

def validate_slug(slug: str) -> str:
    if not re.fullmatch(r'[a-z0-9_-]{3,64}', slug):
        raise ValueError(f"Invalid project slug: {slug!r}")
    return slug

def get_state_path(slug: str) -> Path:
    validate_slug(slug)
    memory_root = Path(os.environ["MEMORY_ROOT"])   # from .env only
    path = memory_root / slug / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def write_state(slug: str, data: dict) -> None:
    target = get_state_path(slug)
    data["project_slug"] = slug          # load guard field
    data["schema_version"] = "1"
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix="state_tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())         # survive VPS power loss
        os.replace(tmp, target)          # atomic POSIX rename
    except Exception:
        if os.path.exists(tmp): os.unlink(tmp)
        raise

def read_state(slug: str) -> dict:
    path = get_state_path(slug)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if data.get("project_slug") != slug: # load guard
        raise ValueError(f"State file slug mismatch: expected {slug}")
    return data

def cleanup_tmp_files(slug: str) -> None:
    """Remove orphaned state_tmp_*.json from crashed writes."""
    for f in get_state_path(slug).parent.glob("state_tmp_*.json"):
        f.unlink(missing_ok=True)
```

```python
# orchestrator.py — ProjectContext (replaces direct state.json calls)

class ProjectContext:
    def __init__(self, slug: str):
        self.slug = slug
        cleanup_tmp_files(slug)
        self.state = read_state(slug)   # {} on first run

    def save(self) -> None:
        write_state(self.slug, self.state)

# Sequential loop:
for task in project_queue:
    ctx = ProjectContext(slug=task.slug)
    try:
        run_project(ctx)
        ctx.save()
    except Exception as e:
        ctx.state["last_error"] = str(e)
        ctx.save()
    finally:
        del ctx   # explicit RAM release — 2GB VPS discipline
```

**Add to .env.example:**
```
MEMORY_ROOT=./memory   # where per-project state lives (outside workspace)
```

**Failure modes handled:**
- git clean -fd rollback → state survives (outside workspace)
- Agent hallucination deletes workspace → state survives
- Mid-write VPS crash → state_tmp_*.json cleaned on next startup
- Wrong slug passed → load guard raises ValueError immediately
- Orphaned state after project delete → purge_project(slug) cleans memory/{slug}/

**Build gate:** no gate — standalone change, safe to build anytime.
**Size:** ~40 lines state_manager.py + ~15 lines orchestrator.py
**Dependencies:** os, json, re, tempfile, pathlib — stdlib only. Zero new installs.
**Done condition:** pytest passes + test slug="../../evil" raises ValueError +
  test two projects write to separate paths + test load guard rejects wrong slug +
  test state survives after git clean -fd simulation (delete workspace dir).

---

### FIX-3c — Tiered Complexity Gates (replaces flat 50-line limit)

**Files:**
- `phase3/complexity_gate.py`     NEW — ~40 lines
- `phase3/orchestrator.py`        MOD — replace flat line check with complexity_gate()

**Source:** Perplexity Sonnet + ChatGPT o4 + Gemini 2.5 Pro research (2026-03-28)

**What is broken:**
Flat 50-line limit treats all files identically.
A 90-line config.py with 20 settings gets rejected — wastes a retry.
A 35-line service.py with 4 nested branches + 3 side effects passes — fails pytest.
Lines measure string length. Hallucination correlates with decision points, not line count.

Math proof (Gemini 2.5 Pro):
```
P_success = 0.999^N  (per-token accuracy compounded)
50 lines  (~500 tokens)  = 60.6% pass rate
100 lines (~1000 tokens) = 36.7% pass rate  ← why logic files MUST stay at 50
```

**What changes — three-axis gate per file type:**

```python
# phase3/complexity_gate.py

FILE_TYPE_GATES = {
    # file_type: (max_lines, max_cc, max_functions)
    "config":    (100,  3,  3),
    "model":      (90,  5,  5),
    "schema":     (85,  3,  4),
    "test":      (120,  5, 10),
    "route":      (55,  8,  4),
    "service":    (50, 10,  3),
    "util":       (65,  7,  5),
    "migration": (120,  2,  3),
    "scaffold":  (100,  2,  5),
    "default":    (50, 10,  3),  # unrecognised → strictest
}

def detect_file_type(file_path: str) -> str:
    name = Path(file_path).name.lower()
    if name.startswith("test_"):              return "test"
    if "config" in name:                      return "config"
    if "schema" in name:                      return "schema"
    if "model" in name:                       return "model"
    if "route" in name or "endpoint" in name: return "route"
    if "migration" in name:                   return "migration"
    if "util" in name or "helper" in name:    return "util"
    return "service"  # strictest default

def complexity_gate(source: str, file_path: str) -> tuple[bool, str]:
    file_type = detect_file_type(file_path)
    max_lines, max_cc, max_funcs = FILE_TYPE_GATES[file_type]
    lines = source.count('\n')
    cc    = get_max_cc(source)       # radon — already in pipeline
    funcs = count_functions(source)  # ast   — already in pipeline
    if lines > max_lines:
        return False, f"lines={lines} exceeds {max_lines} for {file_type} — split into smaller file"
    if cc > max_cc:
        return False, f"cyclomatic_complexity={cc} exceeds {max_cc} — simplify branches"
    if funcs > max_funcs:
        return False, f"functions={funcs} exceeds {max_funcs} for {file_type} — extract to separate module"
    return True, "ok"
```

**Where it plugs in (Gate 4 after existing FIX-9 gates):**
```
_call_deepseek()
    ↓
Gate 1 — placeholder check  (FIX-9)
Gate 2 — syntax check       (FIX-9)
Gate 3 — import validation  (FIX-9)
Gate 4 — complexity_gate()  ← FIX-3c NEW
    ↓
write_file()
```

**What this unlocks:**
```
Before: config.py 80 lines → REJECTED (wastes retry)
After:  config.py 80 lines, CC=1, 2 funcs → PASSES (correct)

Before: service.py 40 lines, CC=12 → PASSES → fails pytest
After:  service.py 40 lines, CC=12 → REJECTED "simplify branches" (correct)

Before: test_api.py 110 lines → REJECTED
After:  test_api.py 110 lines, CC=3 → PASSES (correct)
```

Rejection message is specific + actionable → feeds retry prompt directly.
Satisfies "each retry prompt MUST differ" rule automatically.

**Build gate:** after FIX-3b complete.
**Size:** ~40 lines new (complexity_gate.py) + ~5 lines mod in orchestrator.py
**Dependencies:** radon + ast — both already in pipeline (FIX-9). Zero new installs.
**Done condition:** pytest passes + test that config.py 90 lines passes gate + service.py CC=12 rejected with correct message.

---

---

## FROM CLAUDE CODE LEAKED SOURCE — FIX-20 through FIX-24
## Source: claude-code-main/ (cloned 2026-03-31) + mintlify how-it-works page
## Pattern origin noted per fix. All adapted to Python + DeepSeek stack.

---

### FIX-20 — Memoized Context Blocks (prompt token savings)

**Files:**
- `phase3/orchestrator.py`    MOD — _build_agent_x_prompt() cache layer (~8 lines)

**Source:** Claude Code `query.ts` + `utils/api.ts` — `prependUserContext` / `appendSystemContext`
both use `lodash/memoize` so system context is not rebuilt on every API call.

**What is broken:**
`_build_agent_x_prompt()` calls `_run_ast_mapper()` + `vault.get_context_block()` on every task.
On Task 8 of a 12-task project: `global_interfaces` has not changed since Task 7 wrote models.py.
`skill_vault_block` has not changed either — same goal keyword, same top-3 skills.
Both are rebuilt and re-serialized from scratch. ~300 tokens of identical work per task.

**What changes — ~8 lines, orchestrator.py only:**

```python
# orchestrator.py — add two cache fields to ProjectContext or Orchestrator class

_cached_interfaces_hash: str = ""
_cached_interfaces_block: str = ""
_cached_skill_block: str = ""

def _get_interfaces_block(self, state: SharedState) -> str:
    import hashlib
    current = json.dumps(state.global_interfaces, sort_keys=True)
    h = hashlib.md5(current.encode()).hexdigest()[:8]
    if h != self._cached_interfaces_hash:
        self._cached_interfaces_hash = h
        self._cached_interfaces_block = _format_interfaces(state.global_interfaces)
    return self._cached_interfaces_block

def _get_skill_block(self, task_description: str) -> str:
    # Only changes when description changes — one cache hit per task
    if not self._cached_skill_block:
        self._cached_skill_block = self.vault.get_context_block(task_description)
    return self._cached_skill_block
```

Replace direct calls in `_build_agent_x_prompt()`:
```python
# Before:
interfaces_block = _format_interfaces(state.global_interfaces)
skill_block = self.vault.get_context_block(task.description)

# After:
interfaces_block = self._get_interfaces_block(state)
skill_block = self._get_skill_block(task.description)
```

Invalidation rule:
- `_cached_interfaces_block` → invalidated when md5(global_interfaces) changes (only after write_file succeeds)
- `_cached_skill_block` → invalidated when a new task starts with a different description
- Both reset on project start (ProjectContext __init__)

**Impact:**
- Task 2-12: ~300 tokens saved per task on rebuild avoidance
- 12-task project: saves ~3,000 tokens = ~$0.003 per project at DeepSeek prices
- Bigger gain: `_run_ast_mapper()` is IO + CPU. Skipping 10/12 calls on a 12-task project
  cuts orchestrator wall-clock time by ~15% on slow VPS disk.

**Build gate:** no gate — standalone, zero risk.
**Size:** ~8 lines in orchestrator.py. Zero new files.
**Dependencies:** hashlib — stdlib. Zero new installs.
**Done condition:** pytest passes + test that interfaces_block is NOT rebuilt when global_interfaces
  unchanged between tasks + test that it IS rebuilt after write_file() updates a model file.

---

### FIX-21 — Large Error Output → Disk Offload

**Files:**
- `phase3/orchestrator.py`    MOD — retry loop error handling (~10 lines)

**Source:** Claude Code `utils/toolResultStorage.ts` → `applyToolResultBudget()` in `query.ts`.
When tool output exceeds `maxResultSizeChars`, Claude Code writes result to disk and sends
a truncated preview + file path pointer to the model instead of the full output.

**What is broken:**
`_run_tests()` captures stdout + stderr and passes the full output to the retry prompt.
On a project with 30 tests and multiple failures, pytest output can be 200-400 lines.
This floods the DeepSeek context on attempt 1, leaving less room for attempt 2 and 3.
By attempt 3 the accumulated error history pushes toward DeepSeek's context limit.
The fix in CLAUDE.md already caps error lines at 20 — but there is no disk offload.
The 200-line output is just silently truncated. The full trace is lost.

**What changes — ~10 lines in retry loop:**

```python
# orchestrator.py — in _retry_loop() or wherever error output is handled

MAX_ERROR_LINES_TO_LLM = int(os.environ.get("MAX_ERROR_LINES", "20"))

def _prepare_error_output(
    error_output: str,
    task_id: str,
    slug: str,
    attempt: int,
) -> str:
    lines = error_output.splitlines()
    if len(lines) <= MAX_ERROR_LINES_TO_LLM:
        return error_output   # fits — send as-is

    # Disk offload
    log_dir = Path(os.environ["MEMORY_ROOT"]) / slug / "task_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"task_{task_id}_attempt_{attempt}.log"
    log_path.write_text(error_output)

    preview = "\n".join(lines[:MAX_ERROR_LINES_TO_LLM])
    return (
        f"{preview}\n"
        f"... [{len(lines) - MAX_ERROR_LINES_TO_LLM} more lines truncated]"
        f"[full log: {log_path}]"
    )
```

Call site in retry loop:
```python
error_for_prompt = _prepare_error_output(
    error_output=test_result.stderr + test_result.stdout,
    task_id=task.task_id,
    slug=state.project_slug,
    attempt=attempt_number,
)
# error_for_prompt replaces raw output in retry prompt
```

**.env.example addition:**
```
MAX_ERROR_LINES=20   # lines of error output sent to DeepSeek per retry
```

**What this gives you:**
- Full error log on disk for debugging (not lost, just not in prompt)
- DeepSeek context stays clean across all 3 attempts
- `_prepare_error_output()` is pure — easy to test

**Build gate:** after FIX-2 (retry loop already tested).
**Size:** ~10 lines in orchestrator.py. Zero new files (uses MEMORY_ROOT from FIX-19).
**Dependencies:** pathlib, os — stdlib. MEMORY_ROOT already required by FIX-19.
**Done condition:** pytest passes + test that 200-line error → file written to task_logs/ +
  prompt receives exactly 20 lines + pointer + test that 10-line error → no file written.

---

### FIX-22 — Retry Context Compaction

**Files:**
- `phase3/orchestrator.py`    MOD — retry loop attempt accumulation (~12 lines)

**Source:** Claude Code `services/compact/autoCompact.ts` — when conversation approaches context
window limit, Claude Code compacts prior messages into a summary before the next API call.
The compaction threshold is `effectiveContextWindow - AUTOCOMPACT_BUFFER_TOKENS (13,000)`.
Claude Code measured: p99.99 compact summary output = 17,387 tokens → reserves 20k for summary.

**What is broken:**
Agent-X retry loop accumulates context across 3 attempts:
```
Attempt 1: system_prompt + task_prompt + attempt_1_output  (grows)
Attempt 2: all of above + rejection_reason_1 + attempt_2_output  (grows more)
Attempt 3: all of above + rejection_reason_2 + attempt_3_output  (largest)
```
By attempt 3 on a complex task: accumulated context can reach 8,000-12,000 tokens.
DeepSeek-chat context limit = 16,384 tokens. Attempt 3 can fail with context overflow —
not a logic error, not a code error — just the conversation history being too large.
This is the exact failure mode Claude Code's autoCompact was built to solve.

**What changes — ~12 lines in orchestrator.py retry loop:**

No LLM call needed. Python-side compaction: replace prior attempt details with a summary string.

```python
# orchestrator.py — retry accumulator

def _compact_attempt_history(attempts: list[dict]) -> str:
    """Compact prior attempt outputs into a single summary block.
    Called before attempt 3 to prevent context overflow."""
    lines = []
    for i, a in enumerate(attempts, 1):
        # Keep rejection reason (always <5 lines) + first 5 lines of error
        err_preview = "\n".join(a["error"].splitlines()[:5])
        lines.append(f"Attempt {i}: rejected — {a['reason']}. Error: {err_preview}")
    return "Prior attempts summary:\n" + "\n".join(lines)

# In the retry loop:
MAX_RETRIES = 3
accumulated: list[dict] = []

for attempt in range(1, MAX_RETRIES + 1):
    if attempt == MAX_RETRIES and len(accumulated) >= 2:
        # Compact before final attempt — replace full history with summary
        history_block = _compact_attempt_history(accumulated)
    else:
        history_block = _format_full_history(accumulated)

    prompt = _build_retry_prompt(task, history_block, attempt)
    result = _call_deepseek(prompt)
    accumulated.append({"reason": result.rejection_reason, "error": result.error})
```

**Why no LLM compaction call (unlike Claude Code):**
Claude Code compacts by asking Claude to summarize — expensive, adds latency.
Agent-X compaction is deterministic: keep rejection_reason (always short) + first 5 error lines.
No API call. No latency. Same result: attempt 3 context is bounded regardless of attempt 1-2 size.

**Impact:**
Attempt 3 context before FIX-22: 8,000-12,000 tokens (overflow risk on DeepSeek 16k limit).
Attempt 3 context after FIX-22: bounded at ~3,000 tokens (system + task + compact summary).
Hard tasks that currently fail at attempt 3 due to context overflow: fixed.

**Build gate:** after FIX-2 retry loop is clean and tested.
**Size:** ~12 lines in orchestrator.py. Zero new files.
**Dependencies:** none. Pure Python string manipulation.
**Done condition:** pytest passes + test that attempt 3 prompt is shorter than attempt 2 prompt
  + test that compact summary contains rejection_reason from attempt 1 and 2
  + test that attempt 3 not triggered when MAX_RETRIES=1 (no compaction needed).

---

### FIX-23 — Plan Verification Gate (post-build goal check)

**Files:**
- `phase3/orchestrator.py`    MOD — after is_done(), before final Telegram report (~20 lines)

**Source:** Claude Code `tools/VerifyPlanExecutionTool/` — `CLAUDE_CODE_VERIFY_PLAN` feature flag.
After all tasks complete, asks Claude: "Was the original goal actually achieved?"
Returns pass/fail + reason. Used as final quality gate before marking project complete.

**What is broken:**
`is_done()` returns True when all tasks have status DONE or SKIPPED.
This is task completion, not goal completion.
Real failure modes it misses:
- T1 wrote models.py, T4 wrote routes.py — both passed pytest — but main.py never imports routes
  → app starts, no endpoints respond, goal not achieved
- Brief said "with user authentication" — T6 (auth) was skipped by user — goal partially achieved
- All 8 tasks passed — but the FastAPI app raises ImportError on startup — goal not achieved

Agent-X has no mechanism to catch these. Task status = proxy for goal. A bad proxy.

**What changes — one function + one call in run_loop():**

```python
# orchestrator.py

def _verify_goal(state: SharedState, repo_path: Path) -> tuple[bool, str]:
    """One DeepSeek call after is_done(). Checks if brief was satisfied."""
    goal = state.goal
    completed = [t.task_id + ": " + t.description for t in state.plan if t.status == "done"]
    skipped   = [t.task_id + ": " + t.description for t in state.plan if t.status == "skipped"]

    context_md = (repo_path / ".agent" / "context.md").read_text() \
                 if (repo_path / ".agent" / "context.md").exists() else ""

    prompt = f"""Original goal: {goal}

Tasks completed:
{chr(10).join(completed)}

Tasks skipped:
{chr(10).join(skipped) if skipped else "None"}

Project context (what was actually built):
{context_md[:1000]}

Question: Was the original goal fully achieved?
Answer with PASS or FAIL, then one sentence explaining why.
Format: PASS: <reason>  OR  FAIL: <reason>"""

    response = _call_deepseek(prompt, max_tokens=80)
    passed = response.strip().upper().startswith("PASS")
    return passed, response.strip()

# In run_loop(), after is_done():
if is_done(state):
    verified, verdict = _verify_goal(state, repo_path)
    status_emoji = "✅" if verified else "⚠️"
    _telegram_notify(
        f"{status_emoji} Build complete.\n"
        f"Goal check: {verdict}\n"
        f"Tasks: {len(done)} done / {len(skipped)} skipped"
    )
```

**What this catches:**
- Missing wiring (routes never imported into main.py) — FAIL: "FastAPI app has no registered routes"
- Partial skip (auth skipped, goal required it) — FAIL: "Authentication was required but skipped"
- Silent stub leak — FAIL: "context.md shows auth.py still has pass-only body"
- Clean build — PASS: "All CRUD endpoints wired, tests green, app runnable"

**Cost:** one DeepSeek call per completed project. max_tokens=80. ~$0.0001.
**Not a blocker:** FAIL verdict does not halt the build — it notifies. User decides what to do.
This is a diagnostic signal, not a hard gate. Hard gates are within the build loop (FIX-9/FIX-3c).

**Build gate:** after FIX-11 (Telegram notify infrastructure exists).
**Size:** ~20 lines in orchestrator.py. Zero new files.
**Dependencies:** existing DeepSeek client + Telegram notify. Zero new installs.
**Done condition:** pytest passes + test PASS verdict when all tasks done + goal matches context +
  test FAIL verdict when auth task skipped + goal string contains "authentication" +
  test prompt length < 1200 tokens (context_md hard-capped at 1000 chars).

---

### FIX-24 — Auto Memory Extraction (post-project learning)

**Files:**
- `phase3/orchestrator.py`          MOD — call extract_project_memory() after _verify_goal() (~5 lines)
- `memory/auto_extractor.py`        NEW — extract_project_memory() (~30 lines)

**Source:** Claude Code `services/extractMemories/extractMemories.ts` + `prompts.ts`.
After each conversation turn where the main agent did not write memories itself,
Claude Code forks a background memory extraction agent that reads the last N messages
and writes user/feedback/project/reference memories. The extraction agent has read-only
access to conversation + write-only access to memory directory.

**What is broken:**
Agent-X writes to `memory.jsonl` at task boundaries (outcome + Thompson update).
`retrospective.py` extracts skills after `failed_attempts >= 2 then succeeded`.
Neither captures project-level learnings:
- "SQLite + SQLAlchemy sync engine works for this user's typical bot scale"
- "FastAPI + httpx test client: always install httpx[sync] or fixtures fail"
- "This project took 2 iterations — bottleneck was missing __init__.py in tests/"
These are not code patterns (skill_vault territory) and not error traces (memory.jsonl territory).
They are project-level facts. Currently discarded after every project. Lost signal.

**What changes:**

```python
# memory/auto_extractor.py

import json, os
from pathlib import Path
from typing import Any

EXTRACTION_PROMPT = """You are a memory extraction agent for Agent-XYZ.
A project just completed. Extract 1-3 project-level learnings as memory entries.

DO NOT extract:
- Code patterns or snippets (those go to skill_vault.jsonl)
- Per-task error traces (those are already in memory.jsonl)
- Things obvious from the stack (e.g. "FastAPI needs Python")

DO extract:
- Stack decisions that were non-obvious (e.g. "sync not async for this scale")
- Structural patterns that saved or cost iterations
- User preferences revealed during build (e.g. "prefers SQLite over PostgreSQL")
- Project-type-specific gotchas (e.g. "Telegram bots: always handle getUpdates offset")

Project goal: {goal}
Stack used: {stack}
Iterations: {iteration_count}
Outcome: {outcome}
Skipped tasks: {skipped}
Context summary:
{context_summary}

Output JSON array of 1-3 entries, each:
{{"category": "stack_decision|structural|user_pref|gotcha",
  "fact": "one sentence, specific and actionable",
  "applies_to": "project type or stack keyword"}}

Output ONLY the JSON array. No explanation."""

def extract_project_memory(
    state: dict[str, Any],
    context_md: str,
    outcome: str,
    memory_path: Path,
) -> int:
    """One DeepSeek call after project completion. Writes 0-3 entries to memory.jsonl.
    Returns count of entries written."""
    from phase3.deepseek_client import call_deepseek  # existing client

    skipped = [t["task_id"] for t in state.get("plan", []) if t.get("status") == "skipped"]
    prompt = EXTRACTION_PROMPT.format(
        goal=state.get("goal", ""),
        stack=state.get("language", "python"),
        iteration_count=state.get("iteration_count", 1),
        outcome=outcome,
        skipped=", ".join(skipped) if skipped else "None",
        context_summary=context_md[:800],
    )

    raw = call_deepseek(prompt, max_tokens=300)
    try:
        entries = json.loads(raw.strip())
    except json.JSONDecodeError:
        return 0   # malformed → skip silently, never crash

    written = 0
    with open(memory_path, "a") as f:
        for entry in entries[:3]:
            if not isinstance(entry, dict):
                continue
            record = {
                "source": "auto_extractor",
                "project_slug": state.get("project_slug", "unknown"),
                "category": entry.get("category", "unknown"),
                "fact": entry.get("fact", ""),
                "applies_to": entry.get("applies_to", ""),
                "outcome": outcome,
            }
            f.write(json.dumps(record) + "\n")
            written += 1
    return written
```

Call site in `orchestrator.py` — after `_verify_goal()`:
```python
from memory.auto_extractor import extract_project_memory

n = extract_project_memory(
    state=state.model_dump(),
    context_md=context_md,
    outcome="success" if verified else "partial",
    memory_path=Path(os.environ["MEMORY_ROOT"]) / "auto_memory.jsonl",
)
log.info("auto_extractor.done", entries_written=n)
```

**Separate file from memory.jsonl:**
Auto-extracted entries go to `memory/auto_memory.jsonl` (not `memory.jsonl`).
Reason: `memory.jsonl` contains per-task execution traces used for BM25 retrieval.
Auto-extracted entries are project-level facts — different schema, different query path.
When Historical Mandates (v4.2) are built: `auto_memory.jsonl` is the primary source.

**Cost:** one DeepSeek call per completed project. max_tokens=300. ~$0.0003.

**Build gate:** after FIX-23 (post-build hook in orchestrator exists). MEMORY_ROOT from FIX-19.
**Size:** ~30 lines auto_extractor.py + ~5 lines orchestrator.py.
**Dependencies:** existing DeepSeek client + json — stdlib. Zero new installs.
**Done condition:** pytest passes + test that malformed LLM JSON → returns 0, no crash +
  test that 3 valid entries → written to auto_memory.jsonl with correct schema +
  test that entries > 3 → only first 3 written (cap enforced) +
  test auto_memory.jsonl is separate from memory.jsonl (no cross-write).

---

### FIX-25 — Scheduled Project Triggers (cron via brief.yaml)

**Files:**
- `phase3/brief_watcher.py`     MOD — read `schedule:` field from brief.yaml (~8 lines)
- `phase3/scheduler.py`         NEW — register_cron(), list_crons(), cancel_cron() (~25 lines)

**Source:** Claude Code `tools/ScheduleCronTool/` — `CronCreateTool` with 5-field cron syntax,
auto-expiry after 7 days, jitter for load distribution, one-shot mode (recurring: false).
Claude Code uses this for: recurring remote agents, scheduled cleanup, automated deployments.

**What is missing:**
`brief_watcher.py` is file-drop triggered (watchdog on /projects/new/).
Telegram is user-message triggered.
Neither supports time-based triggering: "build this overnight", "retry failed project at 3am",
"run this data pipeline every night at midnight".
Time-triggered builds are the natural extension of the existing trigger system.

**What changes:**

`brief.yaml` gets one optional field:
```yaml
goal: "Build a crypto price alert bot"
schedule: "0 2 * * *"   # optional — standard 5-field cron. Omit for immediate trigger.
# schedule: "once"      # trigger once at next window (30 min from now)
```

```python
# phase3/scheduler.py

import json, os, threading
from pathlib import Path
from datetime import datetime
from croniter import croniter   # pip install croniter — already used in similar projects

CRON_REGISTRY = Path(os.environ.get("MEMORY_ROOT", "./memory")) / "cron_jobs.jsonl"

def register_cron(slug: str, goal: str, cron_expr: str, brief_path: str) -> str:
    """Register a scheduled project trigger. Returns job_id."""
    job_id = f"cron_{slug}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    entry = {
        "job_id": job_id,
        "slug": slug,
        "goal": goal,
        "cron_expr": cron_expr,
        "brief_path": str(brief_path),
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": None,   # None = no expiry (user controls lifecycle)
        "last_triggered": None,
        "status": "active",
    }
    with open(CRON_REGISTRY, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return job_id

def get_due_jobs() -> list[dict]:
    """Return all active cron jobs that are due to run now."""
    if not CRON_REGISTRY.exists():
        return []
    now = datetime.utcnow()
    due = []
    seen_ids = set()
    for line in CRON_REGISTRY.read_text().splitlines():
        try:
            job = json.loads(line)
        except json.JSONDecodeError:
            continue
        if job["job_id"] in seen_ids or job.get("status") != "active":
            continue
        seen_ids.add(job["job_id"])
        last = datetime.fromisoformat(job["last_triggered"]) \
               if job["last_triggered"] else datetime(2000, 1, 1)
        cron = croniter(job["cron_expr"], last)
        if cron.get_next(datetime) <= now:
            due.append(job)
    return due

def cancel_cron(job_id: str) -> None:
    """Mark a cron job as cancelled (append-only log — no rewrite)."""
    with open(CRON_REGISTRY, "a") as f:
        f.write(json.dumps({"job_id": job_id, "status": "cancelled"}) + "\n")
```

`brief_watcher.py` extension (~8 lines):
```python
# In process_brief() — after reading brief.yaml:
schedule_expr = brief.get("schedule")
if schedule_expr:
    job_id = register_cron(
        slug=brief["goal"][:20].lower().replace(" ", "_"),
        goal=brief["goal"],
        cron_expr=schedule_expr,
        brief_path=brief_path,
    )
    _telegram_notify(f"⏰ Scheduled: {brief['goal']}\nCron: {schedule_expr}\nJob: {job_id}")
    return   # do NOT run_loop() now — scheduler will trigger at right time
# else: run_loop() immediately as before
```

Scheduler polling (add to brief_watcher.py main loop — watchdog already polls every 1s):
```python
# Check cron jobs every 60s alongside file watching
if time.time() - last_cron_check > 60:
    for job in get_due_jobs():
        _telegram_notify(f"⏰ Cron trigger: {job['goal']}")
        threading.Thread(target=run_loop, args=(job["slug"],), daemon=True).start()
        _mark_triggered(job["job_id"])
    last_cron_check = time.time()
```

**Design decisions (from Claude Code patterns):**
- No expiry by default (unlike Claude Code's 7-day auto-expiry) — user controls lifecycle via Telegram
- Append-only JSONL log (consistent with memory.jsonl pattern — never rewrite, always append)
- Deduplication via seen_ids on read (same as memory.jsonl dedup pattern)
- croniter not APScheduler — lighter, no background thread needed, no port, no DB

**Telegram commands (extend existing bot):**
```
/crons           → list active scheduled jobs
/cancel <job_id> → cancel a cron job
```

**Build gate:** after FIX-19 (MEMORY_ROOT in .env). Requires brief_watcher.py working.
**Size:** ~25 lines scheduler.py + ~8 lines brief_watcher.py MOD.
**Dependencies:** `croniter` — `uv pip install croniter`. Lightweight, no sub-dependencies.
**Done condition:** pytest passes + test that due job is returned when cron fires +
  test that cancelled job not returned + test that malformed JSONL line skipped silently +
  test that brief with `schedule:` field registers cron and does NOT call run_loop() immediately.
