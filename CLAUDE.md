# CLAUDE.md — Agent-X v1

## GIT RULES (strict — no exceptions)
- ONLY contributor: CH Y SAI SIDDHARDHA <challayagneshsaisiddhardha@gmail.com>
- Claude NEVER commits, NEVER pushes, NEVER creates branches autonomously
- Claude writes code only — user reviews and commits manually
- Every commit must be on branch: agent-x/fix-<step> (not main)
- main branch NEVER touched directly
- No commit happens until ALL tests for that step pass
- Commit message format: [step-N] description of what was built

## PROGRESS TRACKING RULE (every session, no exceptions)
- docs/progress.md is the source of truth for what is done
- Claude MUST update docs/progress.md after every completed file + test run
- Update format: change PENDING → IN PROGRESS → DONE, add test result + date
- If context.md grows beyond 80 lines → move content to docs/modules/<name>.md
- Never let context.md grow — it is an index only

## CI/CD PROTECTION (3 layers — stops errors before GitHub sees them)
Layer 1 — pre-commit hook  : blocks .env commits + hardcoded secrets
Layer 2 — pre-push hook    : runs clean + verify + pytest before every push
Layer 3 — act local runner : simulates exact GitHub Actions runner locally

Setup (run once after cloning):
  bash scripts/install_hooks.sh    → installs pre-push + pre-commit hooks
  choco install act-cli            → installs act for local CI simulation

Push flow (every time):
  make test          → tests pass locally
  make ci            → act simulates GitHub runner (catches runner-only errors)
  git push           → pre-push hook runs one final check → then pushes

## FIRST COMMAND EVERY SESSION (before anything else)
Run this before writing or running ANY code:
  python scripts/verify_env.py
If it fails → run: make clean   then fix what it reports
If it passes → proceed

Common errors it catches BEFORE they waste your time:
  - stale __pycache__ making Python run old bytecode
  - port 8080 already occupied by previous run
  - wrong Python version active
  - missing packages
  - missing env vars (DEEPSEEK_API_KEY etc)

## SESSION START PROTOCOL (follow this every single session, no exceptions)

STEP 1 — Read these files in order before writing a single line of code:
  1. docs/progress.md         → find current status + next pending step
  2. docs/session_prompts.md  → load the full prompt for that step
  3. docs/problems_and_solutions.md → check which P-bugs apply to this step
  4. context.md               → architecture + folder structure

STEP 2 — User will say one of:
  "step 0" / "step 1" / "step 2" ... "step 8"
  → Read docs/session_prompts.md, find that step, execute it fully and exactly.
  → No questions, no back-and-forth. The prompt has everything needed.

STEP 3 — After every file written:
  → Run smoke test or pytest immediately
  → Tests must PASS before moving to next file
  → Update docs/progress.md (PENDING → IN PROGRESS → DONE + test result + date)

STEP 4 — Step is complete only when:
  → All files built
  → All tests pass
  → docs/progress.md updated
  → Tell user: "Step N done. Run: git add . && git commit -m '[step-N] ...'"
  → STOP. Wait for user to commit before starting next step.

## READ THESE FIRST (every session)
- docs/problems_and_solutions.md → all known bugs + concrete fixes
- docs/roadmap.md → exact build order + status tracker
- context.md → system architecture + folder structure

## Current Build Status (2026-03-20) — v1.3 COMPLETE
ALL STEPS DONE — 206 tests passing — memory.jsonl has 51 entries — thompson_state.json active

DONE (all steps, in order):
- Step 0: requirements.txt + phase2 scaffold + fixtures/syn_001..005  (26 tests)
- Step 1: spike/run_spike.py — DeepSeek loop validated end-to-end
- Step 2: phase1/log_fetcher/fetcher.py rebuild (lazy token, sorted ZIP, structlog)
- Step 3: phase2/classifier/ — regex_pass.py + safety_gate.py         (33 tests)
- Step 4: phase2/patch_gen/ — worker.py + sanitiser.py                (19 tests)
- Step 5: phase2/executor/ — runner.py + regression.py                (18 tests)
- Step 6: phase2/memory/store.py                                       (17 tests)
- Step 7: phase2/pipeline.py — all 5 cases logged in memory.jsonl     (7 tests)
- Step 8: phase2/logging_config.py + pinned requirements.txt           (165 total)

NEXT PHASE: v1.1 — see Upgrade Queue below

## Pipeline (strict order)
Observer → LogParser → RegexClassifier → PreSafetyGate
→ ContextBuilder → DeepSeekWorker → PostSafetyValidation
→ Sanitiser → Executor → RegressionCheck
→ DecisionEngine → MemoryStore

## Hard Rules (no exceptions)
1. confidence < 0.85 → observer mode, pipeline STOPS
2. patch > 15 lines → sanitiser rejects, retry with different prompt
3. max 3 retries per failure event (each retry uses failure-context prompt)
4. ALWAYS append to memory/memory.jsonl regardless of outcome (use finally:)
5. shadow branch ONLY: agent-x/fix-<run_id>
6. main branch NEVER touched unless sandbox passes + regression = 0
7. no secrets in code — os.environ only, ALWAYS lazy (inside functions)
8. no cross-imports between phase1/ phase2/ phase3/

## LLM (v1 — DeepSeek only)
from openai import OpenAI
client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
model = "deepseek-chat"
# Prompt must demand raw unified diff only — no markdown, no fences
# DO NOT add fallbacks until v1 runs end-to-end

## Executor (CRITICAL — openclaw CLI does not work as specced)
# openclaw sandbox execute / sandbox run do NOT exist as CLI subcommands
# Use subprocess only:
subprocess.run(["git", "apply", "patch.diff"], cwd=fixture_path, check=True)
subprocess.run(["pytest", "tests/", "--tb=short", "--json-report"], cwd=fixture_path)
# Fixtures: fixtures/syn_001..005/ — each is a real git repo with the buggy file

## Coding Standards
- Python 3.11+ with type hints on every function
- structlog for all logging (JSON format) — no stdlib logging
- Pydantic v2 for all data models
- pytest + fixtures only — run tests after EVERY file written
- every module has if __name__ == "__main__": smoke test
- specific exceptions only — never bare except:
- all env vars read lazily inside functions, never at module level

## Key Decisions (locked until v1 ships)
1. Executor = local subprocess (not openclaw CLI)
2. Fixtures = 5 real git repos in fixtures/syn_001..005/
3. LLM output = always run strip_markdown_fences() before git apply
4. Retry prompt = always includes rejection reason + line count
5. bug_signature = repo:ErrorType:keyword:file
6. Memory dedup = check (repo + bug_signature) before every write
7. Regression = pytest-json-report before/after diff

## v1 Done — SHIPPED 2026-03-20
pipeline.py ran all 5 synthetic cases. All 5 logged in memory/memory.jsonl.
165 tests passing. requirements.txt fully pinned. Structlog unified.

## Upgrade Queue
v1.1 → Context Builder + RAG retrieval          [DONE — Step 9]
v1.2 → Patch quality fix (syn_002/004/005)       [DONE — Step 10]
v1.3 → Thompson Sampling strategy engine         [DONE — Step 11]
        memory/thompson_state.json written, 2 arms active, learning
v1.4 → Embedding classifier (all-MiniLM-L6-v2)  [NEXT — Step 12]
v2.0 → Researcher / Agentic RAG
v2.1 → Local mode / watchdog observer
v2.2 → LLM rotation (Qwen → Kimi fallbacks)
