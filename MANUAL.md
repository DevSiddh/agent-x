# Agent-X + Agent-Y | Engineering Manual
**Author:** CH Y SAI SIDDHARDHA
**Status:** v2.1 in progress — real GitHub webhook integration
**Vision:** Autonomous software engineer. Not a tutorial project.

---

## What This Is

An autonomous CI/CD self-healing system built as the **proving ground** for a larger vision:

```
User gives idea
    ↓
Agent-Y (brain) — thinks, designs architecture, breaks into tasks
    ↓
Agent-X (hands) — builds, tests, fixes its own errors
    ↓
Feedback loop until done
    ↓
Working repo. No human wrote a line of code.
```

CI/CD repair is step 1. The north star is v4.1 — idea in, working repo out.

---

## Architecture

```
GitHub CI fails
    ↓
Phase 1 — Webhook layer
    webhook server (FastAPI + SQLite queue)
    HMAC-SHA256 validation
    log fetcher (ZIP → sorted step logs)
    ↓
Phase 2 — Pipeline (strict order, no exceptions)
    RegexClassifier     → error type + confidence (0.0–1.0)
    PreSafetyGate       → confidence < 0.85? STOP → observer mode
    ContextBuilder      → affected file + 3 past fixes (RAG)
    Agent-Y Reasoner    → strategy via deepseek-reasoner (CoT)
    DeepSeekWorker      → unified diff patch via deepseek-chat
    Sanitiser           → strip fences, validate format, reject > 15 lines
    Executor            → git apply + pytest (subprocess, not openclaw)
    RegressionCheck     → pytest-json-report before/after
    DecisionEngine      → accepted | rejected | escalated | abstained
    ThompsonSampler     → Beta(α,β) per bug_signature, learns win rate
    MemoryStore         → always appends to memory.jsonl (try/finally)
    ↓
Phase 3 — Real webhook integration (v2.1)
    WebhookWorker       → dequeue → filter → dedup → fetch → clean → classify
    LogCleanerReal      → ANSI strip, timestamp removal, failure window extract
    Runner              → poll loop, structlog every run
```

---

## Agent-Y + Agent-X Communication Protocol (v3.0 target)

Designed with strict contracts. Not vague "agents talking."

```
┌─────────────────────────────────────────────────────────┐
│                    SHARED STATE                         │
│  {                                                      │
│    "project_id": "...",                                 │
│    "goal": "...",                                       │
│    "plan": [{"task_id", "status", "output"}],           │
│    "current_task_id": "T2",                             │
│    "artifacts": {"files": [], "logs": []}               │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
         ↓ reads                         ↑ writes result
┌──────────────────┐           ┌──────────────────────────┐
│   Agent-Y        │           │        Agent-X           │
│   (stateless)    │           │     (no thinking)        │
│                  │           │                          │
│  PLAN →          │           │  receives one Task       │
│  NEXT_TASK →     │  ──────►  │  executes it             │
│  REPLAN          │           │  returns done|failed     │
│                  │  ◄──────  │  + artifacts             │
│  CoT reasoning   │           │                          │
│  only here       │           │  repair loop lives here  │
└──────────────────┘           └──────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR                           │
│  Zero intelligence. Enforces loop only.                 │
│                                                         │
│  while not done:                                        │
│      y_output = agent_y(state)   # plan/next/replan     │
│      task = get_next_pending(state)                     │
│      mark_in_progress(task)      # prevent duplicate    │
│      x_output = agent_x(task)    # execute              │
│      update_state(x_output)                             │
│      if failures >= 2: agent_y_replan(state, failure_type)│
└─────────────────────────────────────────────────────────┘
```

**Locked rules:**
- Agent-Y is stateless — reads shared state only, no hidden memory
- One task at a time — no batching
- Every task has acceptance criteria — without it, Agent-X will lie
- REPLAN on 2 consecutive failures — typed: `compile_error | test_failure | patch_apply_error | runtime_error`
- Task granularity: ≤ 1 file OR ≤ 150 lines, ≤ 1 responsibility, testable in isolation
- Hybrid planning: PLAN = skeleton only, NEXT_TASK = dynamic, never full upfront plan

---

## The Dev System

Every session, every project, same flow:

```
YOU TYPE         CLAUDE DOES
─────────────────────────────────────────────────
"step N"     →  reads session_prompts.md → executes step N fully
"audit"      →  reads 12 project files → GREEN/YELLOW/RED report
"scaffold"   →  generates folder structure + Makefile + CI + hooks
"brief"      →  10-section questionnaire → generates 6 project files
"idea [X]"   →  4-gate validation (Gemini→ChatGPT→Perplexity→Claude)
"session end"→  5-point end-of-session checklist
─────────────────────────────────────────────────
EVERY session → reads docs/progress.md FIRST
```

**6 files that define a project:**
```
CLAUDE.md               → rules + pipeline + decisions (litmus-tested)
context.md              → architecture index (80 lines max, never grows)
docs/session_prompts.md → exact build prompt for every step
docs/progress.md        → PENDING | DONE only, with test results
docs/problems_and_solutions.md → every known bug with code solution
docs/roadmap.md         → locked build order
```

**File-type rules that load on demand:**
```
.claude/rules/python.md  → loads only for *.py files
.claude/rules/tests.md   → loads only for tests/**/*.py
.claude/rules/docs.md    → loads only for *.md files
```

**Hooks (100% enforced, not suggestions):**
```
PreToolUse  → blocks rm -rf, reset --hard, push --force
PostToolUse → black auto-format on every .py edit
Notification→ reinjects project context after compaction
```

---

## Anti-Overengineering Constants

Defined before every LLM project, no exceptions:

```
MAX_OUTPUT_LINES      = 15     (lines LLM can return per patch)
MAX_RETRIES           = 3      (attempts per failure event)
RETRY_MUST_CHANGE     = true   (retry prompt must differ)
CONFIDENCE_THRESHOLD  = 0.85   (below = observer mode, pipeline stops)
MIN_CALIBRATION_RUNS  = 20     (before adjusting threshold)
LOG_ALL_SCORES        = true   (always log for data)
```

**The Thompson Rule** — before any data-gated feature:
```
Feature : _______________
Gate    : ___ minimum runs in memory.jsonl
Fallback: _______________ (must be harmless)
Unlock  : _______________

Cannot fill this → not ready to build it.
```

---

## What's Built (2026-03-20)

```
Phase 1   webhook server, HMAC validation, log fetcher, synthetic dataset
          15 + 13 tests passing

Phase 2   classifier, safety gate, context builder (RAG), patch gen,
          sanitiser, executor, regression check, memory store, pipeline
          206 tests passing — 5/5 synthetic cases accepted

Agent-Y   deepseek-reasoner reasoning layer at step 5.5
          27 tests — validate_strategy, _filter_files, ReasonerError fallback

v1.3      Thompson Sampling — Beta(α,β) per bug_signature
          memory/thompson_state.json active

v2.1      Real GitHub webhook integration (IN PROGRESS)
          Dev environment fully set up — live event queued — Step B0 ready
```

---

## Model Stack

```
Agent-Y (reasoning)   → deepseek-reasoner  (CoT, strategy, architecture)
Agent-X (execution)   → deepseek-chat      (code gen, unified diffs)
Executor              → local subprocess   (git apply + pytest, no cloud sandbox)
```

**Local model path (v4.0 — data-gated):**
```
DeepSeek generates Y→X→Y execution traces
    ↓
Filter + curate (accepted decisions only — garbage in = garbage model)
    ↓
Fine-tune Qwen2.5-7B on curated dataset
    ↓
Proprietary Agent-Y — runs offline, reasons in your exact style
```
Trigger: sensitive code in pipeline OR 50+ successful full loops collected.

---

## Roadmap

```
v2.1  → Real webhook repair         ← HERE (Step B0 ready)
v2.2  → Auto-PR                     (gate: 20+ real accepted fixes)
v2.3  → Multi-repo support
v3.0  → Orchestrator + Plan/Task loop (Y designs, X executes, feedback)
v3.1  → Project memory (goal + architecture + build state)
v4.0  → Fine-tune local model on prompt stack
v4.1  → Idea in → working repo out  ← NORTH STAR
```

---

## The 10 Laws

```
 1. Define done condition before writing line 1
 2. Find all problems before writing any code
 3. Verify external dependencies actually exist (spike first)
 4. Run a spike before building the full system
 5. Env vars lazy — os.environ.get() inside functions, never at module level
 6. Tests pass before moving to next step — no exceptions
 7. Never trust LLM output format — always sanitise, strip, validate
 8. make clean before every test run — stale cache lies
 9. main branch is sacred — shadow branches only
10. Update progress.md after every step — next session must not start blind
```

---

## Stack

```
Python 3.11+     type hints on every function
FastAPI          webhook server
SQLite           queue + dedup store
Pydantic v2      all data models
structlog        JSON logging only (never stdlib logging)
deepseek-chat    patch generation
deepseek-reasoner strategy reasoning
pytest           tests after every file, never skipped
pathlib          everywhere — no string path concat
```

---

## Running It

```bash
# Verify environment first
python scripts/verify_env.py

# Start webhook server (always with --env-file)
python -m uvicorn phase1.webhook.server:app --port 8000 --env-file .env

# Run pipeline on synthetic cases
python phase2/pipeline.py

# Run full test suite
python -m pytest tests/ --tb=short -q

# Run Thompson Sampling spike
python phase2/strategy/thompson.py
```

---

## Repo Structure

```
agent-x/
├── phase1/
│   ├── webhook/          server.py, hmac_validator.py
│   ├── log_fetcher/      fetcher.py, cleaner.py
│   └── dataset/          synthetic.jsonl, schema.py
├── phase2/
│   ├── classifier/       regex_pass.py, safety_gate.py
│   ├── patch_gen/        worker.py, sanitiser.py
│   ├── executor/         runner.py, regression.py
│   ├── memory/           store.py
│   ├── strategy/         thompson.py
│   ├── context_builder.py
│   └── pipeline.py
├── phase3/               (v2.1 — in progress)
│   ├── log_cleaner_real.py
│   ├── webhook_worker.py
│   └── runner.py
├── agent_y/
│   └── reasoner.py       ReasonerOutput, validate_strategy, _filter_files
├── spike/                throwaway validators (never imported)
├── fixtures/             syn_001..005/ — real git repos
├── tests/                206 passing
├── memory/
│   ├── memory.jsonl      append-only run history
│   └── thompson_state.json
├── docs/
│   ├── vision.md         north star + full protocol spec
│   ├── progress.md       live build tracker
│   ├── session_prompts.md step-by-step build prompts
│   ├── problems_and_solutions.md  P1-P19 with code solutions
│   └── v21_roadmap.md    Steps B0-B3
├── .claude/
│   ├── settings.json     hooks (100% enforced)
│   └── rules/            python.md, tests.md, docs.md
├── CLAUDE.md             project rules + pipeline + decisions
├── context.md            architecture index (80 lines)
└── MANUAL.md             ← you are here
```

---

## Why This Exists

Most agent projects are demos. They work once, in a notebook, on a clean example.
This one is built to not collapse after 20 iterations.

The difference:
- Deterministic state machine, not vibes-based prompting
- Every decision logged, every confidence score tracked
- Thompson Sampling learns what actually works, not what sounds good
- Data gates prevent building features before there's signal to support them
- Strict contracts between agents — no hallucination loops

Solo developer. Production-grade architecture. Ship fast, prepare deeply.

---

*Full vision + protocol spec → `docs/vision.md`*
*Build status → `docs/progress.md`*
*To continue building → say "step B0"*
