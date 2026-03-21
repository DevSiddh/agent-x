# Project Skeleton Template
# By: CH Y SAI SIDDHARDHA
# Born from: Agent-X v1 — 2026-03-20
#
# HOW TO USE IN FUTURE PROJECTS:
# Tell Claude: "I have a new project idea. Use docs/PROJECT_TEMPLATE.md
#               as the skeleton. Here is my idea: [your idea]"
# Claude will scaffold everything in under 10 minutes.

---

## THE BUILD FLOW (every project follows this)

```
YOUR IDEA
    │
    ▼
"idea" ──► 4-gate validation
    │       Gate 1 Gemini    : expand possibilities
    │       Gate 2 ChatGPT   : find constraints
    │       Gate 3 Perplexity: verify reality
    │       Gate 4 Claude    : ship or kill
    │       FAIL any gate ──► park in graveyard
    │       PASS all 4   ──► continue
    ▼
"brief" ──► fill CONTEXT_PROMPT_TEMPLATE (15 min)
    │        Claude generates 6 files from your answers
    ▼
"scaffold" ──► folder + Makefile + CI + hooks created
    ▼
PHASE 0 ──► define ALL constants before code
    │        MAX_OUTPUT_LINES, MAX_RETRIES, CONFIDENCE_THRESHOLD
    │        data gates for any ML/stats features
    ▼
STEP 0 ──► spike (50 lines, throwaway)
    │        FAIL ──► fix assumption, re-spike
    │        PASS ──► continue with confidence
    ▼
STEP N ──► build one module
    │        write code → smoke test → pytest → update progress.md
    │        tests PASS ──► commit ──► next step
    │        tests FAIL ──► fix, never move on
    ▼
"audit" ──► run at every phase boundary
    ▼
DONE CONDITION MET ──► ship
```

---

## WHAT THIS TEMPLATE GIVES YOU

Before writing a single line of code you will have:
- Full architecture mapped
- All bugs identified + solutions written
- Build order locked (no random jumping)
- Session prompts ready (just say "step N")
- CI/CD protection (3 layers)
- Stale state prevention (make clean + verify_env)
- Git rules enforced (no accidents)
- Progress tracking (never lose context across sessions)
- Zero hope-driven engineering — every problem has a known solution

---

## PHASE 0 — BEFORE ANY CODE (do this first, always)

### Step A — Define the Mission (context.md)
Answer these before anything else:

```
Mission:          What does this system do in one sentence?
Research Question: What are you trying to prove?
Input:            What goes in?
Output:           What comes out?
Done Condition:   Exactly when is v1 complete? (be specific)
```

Rule: If you cannot answer "done condition" precisely, you are not ready to build.

### Step B — Map the Architecture
Draw the pipeline as a linear flow:
```
Input → Stage1 → Stage2 → Stage3 → Output
```
Every stage must have:
- One clear responsibility
- One clear input type
- One clear output type
- A failure mode (what happens when it breaks?)

### Step C — Identify ALL Problems Before Building
For every stage ask:
1. What external dependency does this need? (API? CLI? Service?)
   → Does it actually exist? Verify before assuming.
2. What happens if the input is malformed?
3. What happens if the external call fails?
4. What env vars does it need? Are they read lazily or at import?
5. What is the retry strategy?
6. What gets written to disk? Can it go stale?

Document every problem in docs/problems_and_solutions.md
Write the concrete solution before writing the code.

### Step D — Run a Spike Before Building
Before building 8 modules — prove the core loop works in 50 lines.
Throwaway script. No tests needed. Just prove the idea is real.
If spike fails → fix the assumption, then build.
If spike passes → build with full confidence.

---

## FOLDER STRUCTURE (copy this for every project)

```
project-name/
│
├── CLAUDE.md                    ← session protocol, git rules, build status
├── context.md                   ← architecture index (max 80 lines, never grows)
├── .env.example                 ← all env vars listed, no values
├── .python-version              ← pin Python version (e.g. 3.11)
├── .gitignore                   ← secrets, cache, venv, runtime files
├── .gitattributes               ← LF line endings, no CRLF surprises
├── Makefile                     ← clean, install, test, run, ci, reset
├── requirements.txt             ← all deps pinned with versions
│
├── docs/
│   ├── problems_and_solutions.md  ← every bug + concrete fix (written BEFORE code)
│   ├── roadmap.md                 ← step-by-step build order + status tracker
│   ├── progress.md                ← live status (Claude updates after every step)
│   ├── session_prompts.md         ← one prompt per step (say "step N" to build)
│   └── modules/                   ← one .md per module (max 80 lines each)
│
├── phase1/                      ← data input + ingestion
├── phase2/                      ← core logic + processing
├── phase3/                      ← output + persistence (if needed)
│
├── tests/                       ← one test file per module
├── fixtures/                    ← test data, synthetic cases
├── spike/                       ← throwaway validation scripts
├── scripts/
│   ├── clean.sh                 ← kill ports, wipe cache, remove runtime files
│   ├── verify_env.py            ← check Python version, packages, env vars, ports
│   ├── install_hooks.sh         ← install pre-push + pre-commit git hooks
│   └── run_act.sh               ← simulate GitHub Actions locally before push
│
├── memory/                      ← persistent storage (JSONL append-only)
│
└── .github/
    └── workflows/
        └── ci.yml               ← GitHub Actions (shadow branches only, not main)
```

---

## CLAUDE.md TEMPLATE (copy + fill in)

```markdown
# CLAUDE.md — [Project Name] v1

## CI/CD PROTECTION (3 layers)
Layer 1 — pre-commit hook  : blocks .env + hardcoded secrets
Layer 2 — pre-push hook    : runs clean + verify + pytest before every push
Layer 3 — act local runner : simulates GitHub runner locally

Setup (run once):
  bash scripts/install_hooks.sh
  choco install act-cli

## FIRST COMMAND EVERY SESSION
  python scripts/verify_env.py
  If fails → make clean → fix → retry

## SESSION START PROTOCOL
1. Read docs/progress.md      → find current status
2. Read docs/session_prompts.md → load step prompt
3. Read docs/problems_and_solutions.md → check relevant fixes
4. User says "step N" → execute fully → update progress.md → stop

## GIT RULES
- ONLY contributor: [Your Name] <your@email.com>
- Claude NEVER commits, NEVER pushes
- Shadow branches only: project/fix-<step>
- main NEVER touched directly
- No commit until ALL tests pass

## PROGRESS TRACKING RULE
- docs/progress.md = source of truth
- Claude updates it after every file + test run
- PENDING → IN PROGRESS → DONE

## Current Build Status
DONE: [list what's built]
NEXT: [exact next step]

## Hard Rules (fill in per project)
1. [rule 1]
2. [rule 2]

## Coding Standards
- Python 3.11+ with type hints
- structlog JSON logging (no stdlib logging)
- Pydantic v2 for all models
- pytest + fixtures only
- every module has __main__ smoke test
- specific exceptions only (no bare except)
- env vars lazy inside functions (never at module level)

## v1 Done When
[Exact completion condition — be specific]
```

---

## context.md TEMPLATE (copy + fill in)

```markdown
# [Project Name] | System Context
# Rule: index only, max 80 lines, NEVER grows

## Mission
[One sentence]

## Architecture Flow
Input → Stage1 → Stage2 → ... → Output

## Failure Taxonomy
ErrorType1: description
ErrorType2: description

## Known Test Cases
case_001: description → category → expected fix
case_002: ...

## Folder Structure
project/
├── phase1/   [what it does]
├── phase2/   [what it does]
├── tests/
└── docs/

## Env Variables
VAR1=
VAR2=

## Key Reference Docs
problems + solutions → docs/problems_and_solutions.md
build roadmap        → docs/roadmap.md
session prompts      → docs/session_prompts.md
```

---

## PROBLEMS_AND_SOLUTIONS.md TEMPLATE

For every problem, write this BEFORE coding:

```markdown
### P[N] — [Problem name]
- Phase: [which phase/module]
- File: [exact file]
- Problem: [what goes wrong and why]
- Solution: [concrete code or approach]
  ```python
  # actual fix code here
  ```
- Status: PENDING / IN PROGRESS / DONE
```

Categories to always check:
- External CLIs → do they actually exist? verify first
- Env vars → lazy or import-time? always lazy
- LLM output → never trust format, always sanitize
- Retry logic → does retry change the prompt? it must
- Memory/storage → dedup check before every write
- Exception handling → finally block for critical writes
- Path handling → pathlib only, no string concat
- Port conflicts → cleanup script handles this
- Stale cache → make clean handles this

---

## SESSION_PROMPTS.md TEMPLATE

Each step prompt must contain:

```markdown
## STEP N — [Step Name]

```
[Project context — 2 lines max]

BUILD THIS STEP:

1. [exact file] — [exact function signatures]
   - [specific requirement]
   - [bug fix reference: P-number]

DONE WHEN:
- pytest tests/test_[module].py → all pass
- smoke test runs: python [file].py
- docs/progress.md updated

STOP. Wait for user to commit before step N+1.
```
```

---

## MAKEFILE TEMPLATE (copy this exactly)

```makefile
.PHONY: clean install test run ci hooks reset help

help:
	@echo "clean   Kill ports + wipe stale cache"
	@echo "install Fresh venv + pip install"
	@echo "test    Clean state then run pytest"
	@echo "run     Clean start server"
	@echo "ci      Run GitHub Actions locally (act)"
	@echo "hooks   Install git hooks"
	@echo "reset   Nuclear reset (clean + reinstall venv)"

clean:
	-pkill -f "[your-server-process]" 2>/dev/null || true
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null || true
	rm -f [runtime files e.g. queue.db, report.json]

install:
	python -m venv .venv
	.venv/Scripts/pip install --upgrade pip
	.venv/Scripts/pip install -r requirements.txt

test: clean
	.venv/Scripts/pytest tests/ -v --tb=short

run: clean
	.venv/Scripts/uvicorn [module]:app --port [port] --reload

ci:
	bash scripts/run_act.sh

hooks:
	bash scripts/install_hooks.sh

reset: clean
	rm -rf .venv
	$(MAKE) install
```

---

## verify_env.py CHECKLIST (always include these checks)

```python
# 1. Python version matches .python-version
# 2. All packages in requirements.txt are importable
# 3. Pydantic v2 (not v1)
# 4. No stale __pycache__ in source dirs
# 5. Required port is free
# 6. Required env vars present (warn if missing, fail if critical)
# 7. No stale runtime files (db, report.json etc)
```

---

## CI/CD WORKFLOW TEMPLATE (.github/workflows/ci.yml)

```yaml
name: [Project] CI

on:
  push:
    branches: ["[project]/**"]   # shadow branches only
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - run: pip install -r requirements.txt
      - run: python scripts/verify_env.py
      - run: find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
      - run: pytest tests/ -v --tb=short
        env:
          [ENV_VAR]: ${{ secrets.ENV_VAR }}
```

---

## THE 10 LAWS (apply to every project, no exceptions)

1. **Define done condition before writing line 1**
   Vague done = never done.

2. **Find all problems before writing any code**
   Build with solutions, not hope.

3. **Verify external dependencies actually exist**
   Never assume a CLI, API, or service works until you've proven it.

4. **Run a spike before building the full system**
   50 throwaway lines saves 500 wasted production lines.

5. **Env vars lazy, always**
   `os.environ.get()` inside functions. Never at module level.

6. **Tests pass before moving to next step**
   No exceptions. No "I'll fix it later."

7. **Never trust LLM output format**
   Always sanitize. Always strip. Always validate.

8. **make clean before every test run**
   Stale cache is silent. It will lie to you.

9. **main branch is sacred**
   Shadow branches only. Pre-push hook enforces it.

10. **Update progress.md after every step**
    Future sessions must not start blind.

---

## HOW TO GIVE THIS TO CLAUDE IN A NEW PROJECT

Tell Claude exactly this:

```
I have a new project: [describe your idea in 3-5 sentences]

Use docs/PROJECT_TEMPLATE.md as the complete skeleton.

Before writing any code:
1. Create CLAUDE.md from the template
2. Create context.md from the template
3. Create docs/problems_and_solutions.md — audit all problems first
4. Create docs/roadmap.md — strict build order
5. Create docs/session_prompts.md — one prompt per step
6. Create Makefile, scripts/, .github/workflows/ci.yml
7. Run the spike to validate core loop
8. Only then build phase by phase

My done condition is: [exact completion criteria]
My tech stack is: [Python/Node/etc, frameworks, external APIs]
```

That's it. Claude has everything. You ship in days not weeks.
