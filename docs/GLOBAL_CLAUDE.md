# Global CLAUDE.md — CH Y SAI SIDDHARDHA
# Loaded automatically in EVERY Claude Code session, EVERY project
# Last updated: 2026-03-20

---

## WHO I AM
Developer: CH Y SAI SIDDHARDHA
Email: challayagneshsaisiddhardha@gmail.com
Style: Ship fast, prepare deeply, no hope-driven engineering

---

## SCAFFOLD COMMAND (use for any new project)

When I say "scaffold" or "/scaffold [idea]":
1. Read ~/.claude/templates/scaffold.md for full instructions
2. Ask the 5 questions first
3. Generate complete skeleton from ~/.claude/templates/PROJECT_TEMPLATE.md
4. Create all files in the exact order listed
5. Run verify_env.py + install_hooks.sh
6. Say "step 0" to start building

Template location: ~/.claude/templates/PROJECT_TEMPLATE.md
Scaffold skill:    ~/.claude/templates/scaffold.md

---

## MY GLOBAL STANDARDS (apply to ALL projects, no exceptions)

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
- Always run: python scripts/verify_env.py first
- Always update: docs/progress.md after every step
- Always say "step N" to load session_prompts.md instructions

---

## MY PROJECTS

### Agent-X (active)
Path:     C:/Users/yagne/OneDrive/Desktop/project x/agent-x/
Status:   v1.2 COMPLETE — 187 tests passing, 5/5 accepted
          Steps 0-10 DONE. Next: step 11 (Thompson — LOCKED until 50+ runs)
Docs:     docs/progress.md → current status
          docs/session_prompts.md → say "step N" to build / "audit" for health check
Template: docs/PROJECT_TEMPLATE.md → reusable skeleton for all future projects

---

## GLOBAL RULES

1. Read docs/progress.md at start of every session
2. Never start a new step until previous step tests all pass
3. Update docs/progress.md after every completed file
4. Verify environment before every test run
5. Never commit .env or secrets
6. Never push to main
7. Run make clean before every test run
8. Spike first — prove core loop before building 8 modules

---

## ANTI-OVERENGINEERING CONSTANTS (apply to every project)

These must be defined in CLAUDE.md before building. Learned from Agent-X.

### The Thompson Rule (data-gated features)
Any feature that learns from data needs a data gate BEFORE you build it.
Template (fill per feature):
  Feature: ___  Data gate: ___ runs  Fallback: ___  Unlock: ___
If you can't fill this → you're not ready to build the feature.

### LLM Projects (mandatory)
  MAX_OUTPUT_LINES  → define before worker (default: 15)
  MAX_RETRIES       → define before worker (default: 3)
  RETRY_MUST_CHANGE → retry prompt must differ from initial (always true)
  SANITISE_ALWAYS   → strip + validate LLM output before use (always true)

### Confidence / Classification
  CONFIDENCE_THRESHOLD → define before classifier (default: 0.85)
  MIN_CALIBRATION_RUNS → define when you'll revisit it (default: 20)
  LOG_ALL_SCORES       → always log for calibration (always true)

### Context Window Budget
  CONTEXT_MD_MAX_LINES   = 80   (index only, never grows)
  ERROR_WINDOW_LINES     = 50   (log lines to parser)
  PROMPT_ERROR_LINES_CAP = 20   (error lines in LLM prompt)
  RAG_SIMILAR_LIMIT      = 3    (past examples per query)

### Storage
  DEDUP_ON          → define field(s) before memory store
  STORAGE_NEVER_RAISES → write must never crash pipeline (always true)
