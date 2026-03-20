# /scaffold — Project Skeleton Generator
# Author: CH Y SAI SIDDHARDHA
# Usage: Tell Claude "/scaffold" + your idea
# Claude reads this and generates a complete project skeleton

---

## WHAT THIS DOES

When user says "/scaffold [project idea]" or "scaffold this: [idea]":

1. Ask user these 5 questions FIRST (do not skip):
   - What goes IN to the system? (input)
   - What comes OUT? (output)
   - What is the EXACT done condition for v1?
   - What external APIs / CLIs / services does it need?
   - What is the tech stack? (Python/Node/etc)

2. Then generate the full skeleton using ~/.claude/templates/PROJECT_TEMPLATE.md

3. Create IN ORDER (do not skip any):
   a. CLAUDE.md           (from template — fill in project specifics)
   b. context.md          (architecture index — max 80 lines)
   c. docs/problems_and_solutions.md  (audit ALL problems BEFORE coding)
   d. docs/roadmap.md     (strict build order — numbered steps)
   e. docs/session_prompts.md (one prompt per step — "step N" ready)
   f. docs/progress.md    (status tracker — all PENDING to start)
   g. Makefile            (clean, install, test, run, ci, reset)
   h. .env.example        (all env vars, no values)
   i. .python-version     (pin to 3.11)
   j. .gitignore          (secrets, cache, venv, runtime)
   k. .gitattributes      (LF line endings)
   l. requirements.txt    (all deps — include: structlog, pydantic>=2.0,
                           pytest, pytest-cov, python-dotenv)
   m. scripts/clean.sh
   n. scripts/verify_env.py
   o. scripts/install_hooks.sh
   p. scripts/run_act.sh
   q. .github/workflows/ci.yml
   r. phase1/__init__.py  (and subpackages based on architecture)
   s. spike/              (empty, for validation script)
   t. memory/             (empty, for persistence)
   u. tests/              (empty, tests come with each step)
   v. fixtures/           (empty, populated in step 0)

4. After all files created:
   - Run: python scripts/verify_env.py
   - Run: bash scripts/install_hooks.sh
   - Tell user: "Skeleton ready. Say 'step 0' to start building."

## RULES (same as PROJECT_TEMPLATE.md — always apply)

- Find ALL problems before writing any code
- Write solution for every problem in problems_and_solutions.md
- Verify every external dependency actually exists
- Define spike (core loop validation) as Step 1 always
- Env vars ALWAYS lazy inside functions
- structlog only — no stdlib logging
- Pydantic v2 for all models
- Tests pass before moving to next step
- main branch NEVER touched — shadow branches only
- docs/progress.md updated after every completed file
