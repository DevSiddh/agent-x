# Global CLAUDE.md — CH Y SAI SIDDHARDHA
# Auto-loaded EVERY session, EVERY project
# Last updated: 2026-03-25
# NOTE: Template paths below point to docs/ in this repo (portable setup)

---

## WHO I AM

Developer : CH Y SAI SIDDHARDHA
Email     : challayagneshsaisiddhardha@gmail.com
Style     : Ship fast, prepare deeply, no hope-driven engineering

---

## HOW THIS SYSTEM WORKS

```
YOU SAY          CLAUDE DOES
─────────────────────────────────────────────────────────
"step N"     →  read session_prompts.md → execute step N
"audit"      →  read session_prompts.md AUDIT section → health check
"scaffold"   →  read docs/scaffold.md → ask 5 questions → generate 6 files
"blunders"   →  read docs/BLUNDERS.md → give warning
"brief"      →  read docs/CONTEXT_PROMPT_TEMPLATE.md → ask briefing questions
"idea [X]"   →  DEFAULT: Claude simulates all 4 gates internally — no external tools
"autoresearch [skill]" → read docs/AUTORESEARCH.md → improve that skill
"session end"  →  read docs/SESSION_END_CHECKLIST.md → run all 5 checks
"idea full"  →  run with Gemini/ChatGPT/Perplexity (only if explicitly requested)
"xyz brief"  →  read docs/XYZ_PROJECT_BRIEF.md → ask user to fill it → generate SharedState + tasks + .env.example
─────────────────────────────────────────────────────────
EVERY session → read docs/progress.md FIRST, no exceptions
```

---

## HOW A PROJECT FLOWS

```
NEW IDEA
    │
    ▼
"idea"  ──► 4-gate validation (Gemini→ChatGPT→Perplexity→Claude)
    │         FAIL any gate → park in graveyard
    │         PASS all 4   ↓
    ▼
"brief" ──► fill CONTEXT_PROMPT_TEMPLATE → Claude generates 6 files
    │
    ▼
"scaffold" ──► folder structure + Makefile + CI + hooks
    │
    ▼
"step 0"  ──► spike first → prove core loop in 50 lines
    │           FAIL → fix assumption, re-spike
    │           PASS ↓
    ▼
"step N"  ──► build one module → tests pass → update progress.md → commit
    │         repeat until done condition met
    ▼
"audit"   ──► run before every new phase boundary
    │
    ▼
  SHIP
```

---

## TRIGGER WORD MAP (full reference)

```
┌──────────────────┬───────────────────────────────────────────────┐
│ YOU SAY          │ CLAUDE READS                                   │
├──────────────────┼───────────────────────────────────────────────┤
│ step N           │ docs/session_prompts.md → STEP N section       │
│ audit            │ docs/session_prompts.md → AUDIT section        │
│ scaffold         │ docs/scaffold.md                               │
│ brief            │ docs/CONTEXT_PROMPT_TEMPLATE.md                │
│ idea [X]         │ DEFAULT — Claude simulates all 4 gates internally          │
│ idea full        │ External tools (Gemini/ChatGPT/Perplexity) — explicit only  │
│ blunders         │ docs/BLUNDERS.md                               │
│ autoresearch X   │ docs/AUTORESEARCH.md                           │
│ session end      │ docs/SESSION_END_CHECKLIST.md                  │
└──────────────────┴───────────────────────────────────────────────┘
```

---

## TEMPLATE LOCATIONS

```
docs/
├── scaffold.md                ← scaffold instructions
├── PROJECT_TEMPLATE.md        ← full project skeleton
├── CONTEXT_PROMPT_TEMPLATE.md ← 10-section briefing questionnaire
├── IDEA_VALIDATION.md         ← 4-gate idea validation
├── BLUNDERS.md                ← 15 blunders + safe folder checklist
├── AUTORESEARCH.md            ← skill self-improvement loop
├── MANUAL.md                  ← complete system reference (read once)
├── QUICKSTART.md              ← 10-line cheatsheet (read every session)
├── CORE_FILES.md              ← minimum files per project type
├── SESSION_END_CHECKLIST.md   ← 5-point end-of-session gate
└── XYZ_PROJECT_BRIEF.md       ← Agent-XYZ project brief (say "xyz brief")
```

---

## MY GLOBAL STANDARDS (all projects, no exceptions)

### Code
- Python 3.11+ with type hints on every function
- structlog JSON logging — never stdlib logging
- Pydantic v2 for all data models
- Specific exceptions only — never bare except
- Env vars lazy inside functions — never at module level
- pathlib.Path everywhere — no string path concat

### Tests
- pytest only — run after EVERY file written
- Tests must pass before moving to next file
- Every module has __main__ smoke test

### Git
- I am the ONLY contributor — Claude never commits or pushes
- Shadow branches only: project/fix-<step>
- main branch is sacred — never touched directly
- No commit until ALL tests for that step pass

### Session
- FIRST command every session: python scripts/verify_env.py
- ALWAYS update docs/progress.md after every step
- ALWAYS say "step N" to load exact instructions
- END of every session: type "session end" → Claude runs SESSION_END_CHECKLIST.md

---

## ANTI-OVERENGINEERING CONSTANTS (every project)

```
LLM PROJECTS (mandatory before building):
  MAX_OUTPUT_LINES  = define it    (Agent-X used 15)
  MAX_RETRIES       = define it    (Agent-X used 3)
  RETRY_MUST_CHANGE = always true  (retry prompt must differ)
  SANITISE_ALWAYS   = always true  (strip + validate LLM output)

CONFIDENCE / CLASSIFICATION:
  CONFIDENCE_THRESHOLD  = define it    (Agent-X used 0.85)
  MIN_CALIBRATION_RUNS  = define it    (Agent-X used 20)
  LOG_ALL_SCORES        = always true

DATA-GATED FEATURES (THE THOMPSON RULE):
  Before building any ML/stats feature, fill this:
    Feature: ___  Gate: ___ runs  Fallback: ___  Unlock: ___
  If you cannot fill it → not ready to build it

CONTEXT WINDOW BUDGET:
  context.md          = 80 lines max (index only, never grows)
  error lines to LLM  = 20 lines max
  past fixes in RAG   = 3 max
  log window          = 50 lines max
```

---

## MY PROJECTS

### Agent-X (active)
```
Path   : ~/agent-x/  (WORKSPACE_ROOT in .env)
Status : v3.0 IN PROGRESS — 493 tests passing
         Steps Y-C0 DONE. X-C0 NEXT.
Next   : step X-C0 — Agent-X task mode: write_file() + StateManager + Orchestrator
Docs   : docs/progress.md       → current status
         docs/session_prompts.md → say "step N" or "audit"
```

---

## GLOBAL RULES

```
1. Read docs/progress.md FIRST every session — no exceptions
2. Never start next step until current step tests ALL pass
3. Update docs/progress.md after every completed file
4. Run python scripts/verify_env.py before every test run
5. Never commit .env or secrets — ever
6. Never push to main — shadow branches only
7. Run make clean before every test run
8. Spike first — prove core loop before building modules
9. Define done condition before writing line 1
10. Define data gates before building data features
```
