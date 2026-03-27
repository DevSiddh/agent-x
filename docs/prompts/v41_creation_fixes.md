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

**Prerequisite:** FIX-1 (AST mapper) must exist — without it domains cannot merge.
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
