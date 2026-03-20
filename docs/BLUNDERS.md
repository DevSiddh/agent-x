# BLUNDERS.md
# Author: CH Y SAI SIDDHARDHA
# Born from: Agent-X v1 — real mistakes, real fixes
# Purpose: Open this when something feels wrong or before starting a new project
# Rule: Every entry here cost real time. Read before building, not after.
# Last updated: 2026-03-20

---

## WHICH PROJECT TYPE? (decide before opening anything else)

```
START HERE
    │
    ▼
Will you delete this in a week?
    ├── YES ──► one file only. No structure. Stop here.
    │
    └── NO
         │
         ▼
    Does it use an LLM in the loop?
         ├── YES ──► TYPE 3 ── full structure, no shortcuts
         │               CLAUDE.md + context.md + all 5 docs
         │               + constants before code
         │               + data gates before ML features
         │               + spike before modules
         │
         └── NO
              │
              ▼
         Runs in prod or used by others?
              ├── YES ──► TYPE 2 ── real project structure
              │               CLAUDE.md + context.md
              │               + tests + Makefile + CI
              │
              └── NO ───► TYPE 1 ── personal tool
                              requirements.txt + .env only
```

---

## WHEN TO OPEN THIS FILE

- Before starting any new project (takes 5 minutes, saves days)
- When a session feels like it's going in circles
- When tests pass but production breaks
- When the project is growing but nothing is shipping
- When you're about to add a "smart" feature

---

## WHERE NOT TO USE THE PROJECT STRUCTURE AT ALL

Do NOT add CLAUDE.md, phases, session prompts, or roadmap to:
- Jupyter notebooks / data exploration
- One-off scripts you run once and delete
- Learning exercises / tutorials
- Copy-paste utilities
- Anything you'll throw away in a week

Adding structure to a throwaway script is overengineering.
A seatbelt on a bicycle. Don't do it.

---

## THE BLUNDERS

---

### B1 — Structure Before Clarity

**What happens:**
You create CLAUDE.md, context.md, phases, roadmap — before you can answer:
- What goes in?
- What comes out?
- When is v1 exactly done?

The structure becomes fiction. Claude fills gaps with assumptions. You build the wrong thing with perfect documentation.

**The fix:**
Answer these 3 before creating any file:
```
Input  (exact format):
Output (exact format):
Done condition (specific, measurable):
```
If you can't answer all 3 in one sentence each — stop. No file helps you yet.

---

### B2 — progress.md Becomes a Diary

**What happens:**
```
Tried X, didn't work
Tried Y, partial success
Thinking about Z
Maybe refactor first
```
Now it's useless. Claude reads it and gets confused. You read it and get confused.

**The fix:**
progress.md has two states only — PENDING or DONE.
Nothing in between lives there.
If it's not done, it's pending. That's it.

---

### B3 — CLAUDE.md Becomes a Novel

**What happens:**
You keep adding rules session after session.
It grows to 300 lines.
Claude stops reading it carefully after 80 lines.
The rules exist but aren't followed.

**The fix:**
Hard rule: if a rule isn't enforced by a test or a git hook — it doesn't belong in CLAUDE.md.
Words without enforcement are wishes, not rules.

---

### B4 — Problems Without Solutions

**What happens:**
```
P7 — API sometimes returns null
Status: PENDING
```
No solution written. Just a worry list.
Next session Claude sees it, doesn't know what to do, guesses.

**The fix:**
Never write a problem without its concrete fix.
If you don't know the fix yet — don't write the problem yet.
problems_and_solutions.md is a solutions doc, not a bug tracker.

---

### B5 — Session Prompts That Are Vague

**What happens:**
```
## Step 3 — Build the classifier
Build a classifier that classifies errors well.
```
Claude interprets "well" 10 different ways.
You get something that works but not what you needed.
You spend the next session fixing it.

**The fix:**
Every step prompt must have:
- Exact file names
- Exact function signatures
- Exact done condition
- Exact test command to run

Rule: if Claude can ask a clarifying question about the step — the prompt is not finished.

---

### B6 — Building Before the Spike

**What happens:**
You write 6 modules assuming the LLM returns clean output.
Spike reveals it wraps everything in markdown fences.
Now you retrofit sanitisation into 6 modules.
2 days wasted.

**The fix:**
Spike first. Always. No exceptions.
50 throwaway lines prove the core loop before investing in 8 modules.
If spike fails → fix the assumption, then build.
If spike passes → build with full confidence.

Agent-X example: spike revealed LLM cannot patch blind — file content required in prompt.
That one finding changed the entire ContextBuilder design.

---

### B7 — Phases That Don't Match Reality

**What happens:**
You design:
```
phase1/ → data ingestion
phase2/ → core logic
phase3/ → output
```
Then phase1 needs to call phase2 to validate something.
Circular imports. Cross-phase dependencies. Architecture breaks.

**The fix:**
Draw the data flow on paper before writing a file.
If any arrow goes backwards — your phases are wrong.
Fix the design, not the imports.

Rule: data flows in one direction only. If it doesn't, you have a design problem not a code problem.

---

### B8 — The Upgrade Queue Forgotten

**What happens:**
You lock Thompson Sampling until 50 runs (smart decision).
3 weeks later you forget it exists.
You build something similar from scratch without the data gate.
Wasted effort.

**The fix:**
Upgrade queue lives in CLAUDE.md with:
- Feature name
- Unlock condition (specific, checkable)
- What it does before unlock (must be harmless)

Not in your head. Not in a note. In CLAUDE.md.
Every new session, Claude reads it and knows what's locked and why.

---

### B9 — requirements.txt Left Unpinned

**What happens:**
```
openai>=1.0.0
pydantic>=2.0
```
6 months later a fresh install pulls newer versions.
Something breaks silently. You spend a day debugging a version conflict.

**The fix:**
Pin on the day you ship. Takes 2 seconds:
```
pip freeze > requirements.txt
```
Do it once after every step that adds a dependency.
Never leave `>=` in a shipped project.

---

### B10 — Committing .env

**What happens:**
Moving fast. Type `git add .`
.env goes in. Push. GitHub scans for secrets.
API key compromised in minutes.
You spend hours rotating keys across every service.

**The fix:**
`.env` in `.gitignore` on day 0.
Pre-commit hook blocks it as layer 2.
`.env.example` in repo with all var names, no values.
No exceptions. Ever. Not even once.

---

### B11 — Retry Sends the Same Prompt

**What happens:**
LLM returns bad output.
You retry with the exact same prompt.
Same output. Same failure. 3 retries wasted. API cost burned.

**The fix:**
Every retry MUST change the prompt.
Include: what was rejected + why + what to do differently.
If the prompt doesn't change — the output won't change.

Agent-X rule: retry prompt must contain rejection_reason + format reminder + affected file path.

---

### B12 — Building a Data Feature Without a Data Gate

**What happens:**
You build Thompson Sampling with 5 runs in memory.
It starts at Beta(1,1) — pure random.
You think it's learning. It isn't.
You optimise it. Still random.
Weeks wasted on a feature that needs 50+ runs to matter.

**The fix (The Thompson Rule):**
Before building ANY feature that learns from data, fill this:
```
Feature: ___
Why it needs data: ___
Data gate (minimum runs/examples): ___
What it does before gate opens: ___ (must be harmless)
Unlock condition (checkable): ___
```
If you can't fill this — you're not ready to build the feature.
Build it anyway — but lock it until the gate opens.

---

### B13 — Env Vars at Module Level

**What happens:**
```python
API_KEY = os.environ.get("API_KEY", "")  # top of file
```
Tests set the env var AFTER import.
The var is always empty in tests.
Tests fail for mysterious reasons.
You spend an hour debugging something that isn't a bug.

**The fix:**
```python
def _get_api_key() -> str:
    key = os.environ.get("API_KEY", "")
    if not key:
        raise EnvironmentError("API_KEY not set")
    return key
```
Read lazily, inside functions, every time.
Never at module level. Never.

---

### B14 — Tests That Only Test the Happy Path

**What happens:**
Every test passes a valid input and checks valid output.
Production sends malformed data.
Nothing crashes during tests.
Everything crashes in production.

**The fix:**
For every module, write at least one test for:
- Missing input
- Malformed input
- External call fails
- Write to disk fails

If your test suite has no failures in the inputs — it's incomplete.

---

### B15 — context.md That Grows

**What happens:**
You keep adding to context.md because "Claude needs to know this."
It grows to 200 lines.
Now it costs more tokens than it saves.
Claude reads the start, skips the end.

**The fix:**
context.md is an index, not documentation.
80 lines maximum. Hard rule. Never broken.
If something needs more explanation → create docs/modules/<name>.md
context.md points to it. It does not contain it.

---

## THE SAFE FOLDER CHECKLIST

Before declaring a project folder complete, verify:

```
[ ] .env in .gitignore (day 0, not day 10)
[ ] .env.example exists with all var names
[ ] requirements.txt fully pinned with ==
[ ] All env vars read lazily inside functions
[ ] Spike run and passed before full build
[ ] Every problem in problems_and_solutions.md has a concrete fix
[ ] Every step in session_prompts.md has exact function signatures + done condition
[ ] context.md is under 80 lines
[ ] progress.md has only PENDING or DONE (no diaries)
[ ] CLAUDE.md rules are enforced by tests or hooks (not just words)
[ ] Upgrade queue has unlock conditions (not just names)
[ ] Data-gated features have data gates defined
[ ] Pre-commit hook blocks .env commits
[ ] Pre-push hook runs tests before push
[ ] main branch has never been touched directly
```

All 15 checked = folder is safe to build from.
Any unchecked = fix it before starting the next session.

---

## ONE LINE SUMMARY

> Every blunder here was caused by moving fast without a gate.
> The structure exists to put gates in the right places.
> Use the gates. Don't skip them. That's the whole system.
