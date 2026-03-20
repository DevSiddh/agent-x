# THE MANUAL
# Author: CH Y SAI SIDDHARDHA
# Purpose: Complete reference for how this AI development system works
# Read this once. Use the trigger words forever.
# Last updated: 2026-03-20

---

## WHAT YOU BUILT

```
┌─────────────────────────────────────────────────────────────┐
│          AN AI-NATIVE DEVELOPMENT OPERATING SYSTEM          │
│                                                             │
│  Not just prompts. Not just files. A complete system that:  │
│  - Validates ideas before you build them                    │
│  - Generates project structure in 20 minutes                │
│  - Keeps Claude consistent across sessions and months       │
│  - Prevents overengineering before it happens               │
│  - Audits your system at any phase boundary                 │
│  - Gets smarter every project you ship                      │
└─────────────────────────────────────────────────────────────┘
```

---

## PART 1 — THE FULL SYSTEM MAP

```
YOUR BRAIN (curiosity + interests + problem)
    │
    ▼
┌─────────────────────────────────────────────┐
│              IDEA LAYER                     │
│  "idea" trigger → IDEA_VALIDATION.md        │
│                                             │
│  Gate 1 Gemini     : expand possibilities   │
│  Gate 2 ChatGPT    : find constraints       │
│  Gate 3 Perplexity : verify reality         │
│  Gate 4 Claude     : ship or kill           │
│                                             │
│  FAIL any gate → IDEAS GRAVEYARD            │
│  PASS all 4    → continue                   │
│                                             │
│  Claude-only fallback: If Gemini/ChatGPT/   │
│  Perplexity unavailable, type:              │
│  "idea solo — [your idea]" and Claude       │
│  simulates all 4 gates internally.          │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│              BRIEF LAYER                    │
│  "brief" trigger → CONTEXT_PROMPT_TEMPLATE  │
│                                             │
│  10 sections. You answer. Claude generates: │
│  → CLAUDE.md        (rules + status)        │
│  → context.md       (architecture index)    │
│  → problems_and_solutions.md                │
│  → roadmap.md       (build order)           │
│  → session_prompts.md (step N prompts)      │
│  → progress.md      (live tracker)          │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│             SCAFFOLD LAYER                  │
│  "scaffold" trigger → scaffold.md           │
│                                             │
│  Generates full folder:                     │
│  → folder structure  → Makefile             │
│  → .env.example      → .gitignore           │
│  → requirements.txt  → CI workflow          │
│  → verify_env.py     → git hooks            │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│              BUILD LAYER                    │
│  "step 0" → spike (prove core loop)         │
│  "step N" → build one module at a time      │
│                                             │
│  Each step:                                 │
│  write → smoke test → pytest → progress.md  │
│  PASS → commit → next step                  │
│  FAIL → fix here, never move on             │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│              AUDIT LAYER                    │
│  "audit" trigger → session_prompts.md       │
│                    AUDIT section            │
│                                             │
│  Reads 12 files. Reports:                   │
│  → system health (GREEN/YELLOW/RED)         │
│  → critical issues                          │
│  → confirmed working                        │
│  → one next action                          │
└─────────────────────────────────────────────┘
    │
    ▼
  SHIP
```

---

## PART 2 — THE FILES AND WHAT THEY DO

### Auto-loaded (Claude reads without being asked)

```
~/.claude/CLAUDE.md
    │
    ├── WHO YOU ARE (name, style, email)
    ├── TRIGGER WORD MAP (what each keyword does)
    ├── HOW A PROJECT FLOWS (ASCII flow)
    ├── GLOBAL STANDARDS (code, tests, git, session)
    ├── ANTI-OVERENGINEERING CONSTANTS
    │     MAX_OUTPUT_LINES, MAX_RETRIES,
    │     CONFIDENCE_THRESHOLD, DATA GATES
    ├── MY PROJECTS (live status of all active projects)
    └── GLOBAL RULES (10 rules, always enforced)

project/CLAUDE.md
    │
    ├── GIT RULES (shadow branches, never push main)
    ├── PROGRESS TRACKING RULE
    ├── CI/CD PROTECTION (3 layers)
    ├── FIRST COMMAND EVERY SESSION (verify_env.py)
    ├── SESSION START PROTOCOL (4 steps)
    ├── PIPELINE (strict stage order)
    ├── HARD RULES (project-specific)
    ├── CODING STANDARDS
    ├── KEY DECISIONS (locked until v1 ships)
    ├── CURRENT BUILD STATUS
    └── UPGRADE QUEUE (locked features + unlock conditions)
```

### Triggered (Claude reads when you ask)

```
docs/progress.md
    └── live status of every step
        PENDING → IN PROGRESS → DONE
        test results + dates
        Claude updates this after every file

docs/session_prompts.md
    └── STEP 0..N  : exact build instructions per step
        AUDIT      : 12-file health check prompt
        each step has: file names, function signatures,
                       done condition, test command

docs/problems_and_solutions.md
    └── every known bug BEFORE it was written
        P1..PN format
        Problem → Why → Solution (code) → Status
        written before code, not after

docs/roadmap.md
    └── strict build order
        one table per step
        locked — no random jumping

context.md
    └── architecture index (max 80 lines, never grows)
        mission, pipeline flow, folder structure,
        env vars, failure taxonomy, key docs
```

### Template files (your sacred folder)

```
~/.claude/templates/

PROJECT_TEMPLATE.md
    └── complete skeleton for any new project
        build flow ASCII, folder structure,
        CLAUDE.md template, context.md template,
        problems template, session prompts template,
        Makefile template, CI template,
        THE 10 LAWS, CONSTANTS BEFORE CODE,
        AUDIT PROMPT TEMPLATE

IDEA_VALIDATION.md
    └── 4-gate validation before building anything
        Gate 1 Gemini    : expand (prompt included)
        Gate 2 ChatGPT   : constrain (prompt included)
        Gate 3 Perplexity: ground truth (prompt included)
        Gate 4 Claude    : execute (prompt included)
        FINAL SCORECARD
        IDEAS GRAVEYARD

CONTEXT_PROMPT_TEMPLATE.md
    └── 10-section briefing questionnaire
        replaces deep-think model
        fill it → paste to Claude → get 6 files
        Section 1: The Problem
        Section 2: The Solution
        Section 3: The Done Condition
        Section 4: The Pipeline
        Section 5: The Risks
        Section 6: The Spike
        Section 7: Environment + Stack
        Section 8: Hard Rules
        Section 9: Upgrade Queue
        Section 10: Autoresearch Checklist

BLUNDERS.md
    └── 15 real mistakes + exact fixes
        project type decision tree (ASCII)
        B1..B15 each with: what happens + the fix
        15-point safe folder checklist

AUTORESEARCH.md
    └── self-improvement loop for any skill/prompt
        baseline → improve one thing → test → keep/revert
        stop at 95%+ three times in a row

scaffold.md
    └── scaffold skill instructions
        5 questions Claude asks before generating
        exact file creation order
```

---

## PART 3 — THE TRIGGER WORDS (complete reference)

```
┌──────────────────┬─────────────────────────────────────────┐
│ YOU TYPE         │ WHAT CLAUDE DOES                        │
├──────────────────┼─────────────────────────────────────────┤
│ idea             │ Opens IDEA_VALIDATION.md                │
│                  │ Runs you through 4 gates                │
│                  │ Gives SHIP or KILL decision             │
├──────────────────┼─────────────────────────────────────────┤
│ brief            │ Opens CONTEXT_PROMPT_TEMPLATE.md        │
│                  │ Asks 10 sections of questions           │
│                  │ Generates all 6 project files           │
├──────────────────┼─────────────────────────────────────────┤
│ scaffold         │ Opens scaffold.md                       │
│                  │ Asks 5 questions                        │
│                  │ Creates full folder structure           │
│                  │ Makefile + CI + hooks + scripts         │
├──────────────────┼─────────────────────────────────────────┤
│ step 0           │ Opens session_prompts.md STEP 0         │
│                  │ Builds spike — proves core loop         │
│                  │ 50 lines, throwaway, PASS or FAIL       │
├──────────────────┼─────────────────────────────────────────┤
│ step N           │ Opens session_prompts.md STEP N         │
│                  │ Builds exactly what the prompt says     │
│                  │ Tests → progress.md → waits for commit  │
├──────────────────┼─────────────────────────────────────────┤
│ audit            │ Opens session_prompts.md AUDIT section  │
│                  │ Reads 12 project files                  │
│                  │ Reports GREEN/YELLOW/RED + one action   │
├──────────────────┼─────────────────────────────────────────┤
│ blunders         │ Opens BLUNDERS.md                       │
│                  │ Shows project type decision tree        │
│                  │ Lists relevant warnings                 │
├──────────────────┼─────────────────────────────────────────┤
│ autoresearch X   │ Opens AUTORESEARCH.md                   │
│                  │ Runs improvement loop on skill X        │
│                  │ Stops at 95%+ three times in a row      │
└──────────────────┴─────────────────────────────────────────┘
```

---

## PART 4 — HOW TO START A NEW PROJECT (step by step)

```
STEP 1 — Validate the idea (10-15 min)
─────────────────────────────────────
Type: "idea — [your idea in 2-3 sentences]"
Claude runs 4 gates. You get prompts to paste into
Gemini, ChatGPT, Perplexity. Paste results back.
Claude gives SHIP or KILL.

If KILL → idea goes to graveyard. Done.
If SHIP → continue to Step 2.

STEP 2 — Brief Claude (15-20 min)
──────────────────────────────────
Type: "brief"
Claude asks 10 sections of questions.
Answer everything. Skip nothing.
Claude generates 6 files. Review them.

STEP 3 — Scaffold the folder (5 min)
─────────────────────────────────────
Type: "scaffold"
Claude creates full folder structure.
Run: bash scripts/install_hooks.sh
Run: python scripts/verify_env.py
If verify_env passes → ready to build.

STEP 4 — Prove it works (spike)
────────────────────────────────
Type: "step 0"
Claude builds 50-line throwaway script.
Run it. Check output.
FAIL → fix the assumption, re-run spike.
PASS → continue.

STEP 5 — Build module by module
────────────────────────────────
Type: "step 1", "step 2" ... "step N"
Each step: Claude builds → tests pass → you commit.
Never move to next step until tests pass.
Never commit until all tests for that step pass.

STEP 6 — Audit at phase boundaries
────────────────────────────────────
Before starting a new phase: type "audit"
Claude reads 12 files, reports health.
Fix any critical issues before continuing.

STEP 7 — Ship
──────────────
Done condition from CLAUDE.md is met.
All tests pass. memory.jsonl has entries.
You commit. You push. Done.
```

---

## PART 5 — HOW TO RESUME A PROJECT AFTER A BREAK

```
1. Open project folder in Claude Code
2. Claude auto-loads CLAUDE.md → reads progress.md
3. Claude tells you exactly where you left off
4. Type: "step N" (whatever step is PENDING)
5. Build continues. Zero re-explaining.

That's it. The files do the memory.
```

---

## PART 6 — THE 3 PROJECT TYPES

```
TYPE 1 — Personal Tool / Script
────────────────────────────────
Signs  : runs once, solo use, deleted in a week
Files  : script.py + .env + requirements.txt
Trigger: none. Just write it.

TYPE 2 — Real Project, No LLM
──────────────────────────────
Signs  : multiple modules, used by others, runs in prod
Files  : CLAUDE.md + context.md + tests + Makefile + CI
Trigger: "brief" → "scaffold" → "step N"

TYPE 3 — Agent / LLM Pipeline / Learning System
─────────────────────────────────────────────────
Signs  : LLM in the loop, autonomous decisions,
         data accumulates, confidence scoring,
         retries, memory store
Files  : everything. full structure. no shortcuts.
Trigger: "idea" → "brief" → "scaffold" → "step 0"
         → "step N" → "audit" → ship
```

---

## PART 7 — THE CONSTANTS (define before every Type 3 project)

```
LLM CONSTANTS (mandatory)
─────────────────────────
MAX_OUTPUT_LINES     = ?   lines LLM can return    (Agent-X: 15)
MAX_RETRIES          = ?   attempts per event       (Agent-X: 3)
RETRY_MUST_CHANGE    = true  retry prompt must differ (always)
SANITISE_ALWAYS      = true  strip + validate output  (always)

CLASSIFICATION CONSTANTS
────────────────────────
CONFIDENCE_THRESHOLD = ?   below = observer mode    (Agent-X: 0.85)
MIN_CALIBRATION_RUNS = ?   before adjusting          (Agent-X: 20)
LOG_ALL_SCORES       = true  always log for data      (always)

DATA-GATED FEATURES (THE THOMPSON RULE)
────────────────────────────────────────
Before building ANY feature that learns from data:

  Feature : _______________
  Why data: _______________
  Gate    : ___ minimum runs
  Fallback: _______________ (must be harmless)
  Unlock  : _______________

Cannot fill this → not ready to build it.

CONTEXT BUDGET
──────────────
context.md lines     = 80 max   (index only)
error lines to LLM   = 20 max   (token budget)
past fixes in RAG    = 3 max    (token budget)
log window           = 50 max   (parser input)
```

---

## PART 8 — THE 10 LAWS

```
 1. Define done condition before writing line 1
    Vague done = never done.

 2. Find all problems before writing any code
    Build with solutions, not hope.

 3. Verify external dependencies actually exist
    Never assume a CLI, API, or service works.
    Prove it before building around it.

 4. Run a spike before building the full system
    50 throwaway lines saves 500 wasted lines.

 5. Env vars lazy — always
    os.environ.get() inside functions.
    Never at module level. Never.

 6. Tests pass before moving to next step
    No exceptions. No "I'll fix it later."

 7. Never trust LLM output format
    Always sanitize. Always strip. Always validate.

 8. make clean before every test run
    Stale cache is silent. It will lie to you.

 9. main branch is sacred
    Shadow branches only.
    Pre-push hook enforces it.

10. Update progress.md after every step
    Future sessions must not start blind.
```

---

## PART 9 — THE 15 BLUNDERS (quick reference)

```
B1  Structure before clarity
    → answer input/output/done before creating files

B2  progress.md becomes a diary
    → PENDING or DONE only. nothing in between.

B3  CLAUDE.md becomes a novel
    → rules without tests/hooks are just wishes

B4  Problems without solutions
    → never write a problem without its concrete fix

B5  Session prompts that are vague
    → exact signatures + exact done condition required

B6  Building before the spike
    → spike first. always. no exceptions.

B7  Phases that don't match data flow
    → draw arrows first. if any go backwards, redesign.

B8  Upgrade queue forgotten
    → locked features need unlock conditions in CLAUDE.md

B9  requirements.txt unpinned
    → pip freeze after every step that adds a dependency

B10 Committing .env
    → .gitignore day 0. pre-commit hook day 0.

B11 Retry sends same prompt
    → retry must include rejection reason + what to fix

B12 Data feature without data gate (Thompson Rule)
    → fill the gate template before building

B13 Env vars at module level
    → lazy getter function. always. no exceptions.

B14 Tests only cover happy path
    → one failure test per module minimum

B15 context.md that grows
    → 80 lines max. index only. overflow → modules/
```

---

## PART 10 — PLATFORMS: WHERE THIS WORKS

```
┌─────────────────┬────────────────────────────────────────┐
│ PLATFORM        │ HOW TO USE THIS SYSTEM                 │
├─────────────────┼────────────────────────────────────────┤
│ Claude Code     │ Best. CLAUDE.md auto-loads.            │
│ (what you use)  │ Just open folder. Type trigger word.   │
│                 │ Zero setup per session.                │
├─────────────────┼────────────────────────────────────────┤
│ Cursor          │ Paste one starter prompt at session    │
│                 │ start: "Read CLAUDE.md, context.md,    │
│                 │ docs/progress.md then wait."           │
│                 │ Then type trigger words normally.      │
├─────────────────┼────────────────────────────────────────┤
│ GitHub Copilot  │ No CLAUDE.md auto-load.                │
│                 │ Less effective. Use for autocomplete   │
│                 │ only, not session management.          │
├─────────────────┼────────────────────────────────────────┤
│ ChatGPT/Codex   │ Paste CLAUDE.md + context.md content  │
│                 │ as system message. Then use normally.  │
│                 │ Loses context between sessions.        │
├─────────────────┼────────────────────────────────────────┤
│ Any AI tool     │ The docs/ files work everywhere.       │
│                 │ Only the auto-loading is Claude-native.│
│                 │ The system works — just paste manually.│
└─────────────────┴────────────────────────────────────────┘
```

---

## PART 11 — QUICK REFERENCE CARD

```
┌─────────────────────────────────────────────────────────┐
│                    CHEAT SHEET                          │
├─────────────────────────────────────────────────────────┤
│ NEW PROJECT                                             │
│   "idea"     → validate (4 gates)                       │
│   "brief"    → generate 6 files                         │
│   "scaffold" → create folder                            │
│   "step 0"   → spike                                    │
│   "step N"   → build                                    │
├─────────────────────────────────────────────────────────┤
│ EXISTING PROJECT                                        │
│   open folder → Claude reads progress.md automatically  │
│   "step N"   → continue building                        │
│   "audit"    → health check                             │
├─────────────────────────────────────────────────────────┤
│ SOMETHING FEELS WRONG                                   │
│   "audit"    → find the problem                         │
│   "blunders" → check you're not repeating a mistake     │
├─────────────────────────────────────────────────────────┤
│ IMPROVING A SKILL/PROMPT                                │
│   "autoresearch [skill name]"                           │
├─────────────────────────────────────────────────────────┤
│ BEFORE ANY NEW PROJECT (30 second check)                │
│   "blunders" → run the 15-point checklist               │
└─────────────────────────────────────────────────────────┘
```

---

## FINAL NOTE

```
This system was not designed.
It was discovered — one blunder at a time, one project at a time.

Agent-X v1 taught:
  - Spike before modules (B6)
  - Data gates before ML features (B12, Thompson Rule)
  - LLM output always lies about format (B11, sanitiser)
  - Env vars at module level breaks tests (B13)
  - context.md is an index not a doc (B15)

Every future project inherits those lessons automatically.
That is the point of the system.

You don't have to learn the same lesson twice.
```
