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

### Agent-X v1 (active)
Path:     C:/Users/yagne/OneDrive/Desktop/project x/agent-x/
Status:   Phase 1 webhook done (15 tests pass). Step 0 next.
Docs:     docs/progress.md → current status
          docs/session_prompts.md → say "step N" to build
Template: docs/PROJECT_TEMPLATE.md → reusable skeleton

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
