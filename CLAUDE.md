# CLAUDE.md — Agent-X v1.3

## GIT RULES
- ONLY contributor: CH Y SAI SIDDHARDHA <challayagneshsaisiddhardha@gmail.com>
- Claude NEVER commits, NEVER pushes, NEVER creates branches autonomously
- Every commit must be on branch: agent-x/fix-<step> — never main
- No commit until ALL tests for that step pass
- Commit message format: [step-N] description of what was built

## FIRST COMMAND EVERY SESSION
  python scripts/verify_env.py
  Fails → fix what it reports before touching anything

## SESSION START PROTOCOL
1. Read @docs/progress.md         → find current status + next PENDING step
2. Read @docs/session_prompts.md  → load the full prompt for that step
3. Read @docs/problems_and_solutions.md → check which P-bugs apply
4. User says "step N" → execute fully → update progress.md → STOP

## CI/CD PROTECTION (3 layers)
Layer 1 — pre-commit hook  : blocks .env commits + hardcoded secrets
Layer 2 — pre-push hook    : runs verify + pytest before every push
Layer 3 — act local runner : simulates GitHub Actions locally
Setup: bash scripts/install_hooks.sh

## Current Build Status (2026-03-20) — v1.3 COMPLETE
206 tests passing — memory.jsonl has 51+ entries — thompson_state.json active
Full step history → @docs/progress.md

## Pipeline (strict order — do not change)
Observer → LogParser → RegexClassifier → PreSafetyGate
→ ThompsonSampler.sample() → ContextBuilder → DeepSeekWorker → PostSafetyValidation
→ Sanitiser → Executor → RegressionCheck → DecisionEngine
→ ThompsonSampler.update() → MemoryStore

## Hard Rules (no exceptions)
1. confidence < 0.85 → observer mode, pipeline STOPS
2. patch > 15 lines → sanitiser rejects, retry with different prompt
3. max 3 retries per failure event — each retry prompt MUST differ
4. ALWAYS append to memory/memory.jsonl regardless of outcome (use finally:)
5. shadow branch ONLY: agent-x/fix-<run_id>
6. main branch NEVER touched unless sandbox passes + regression = 0
7. no secrets in code — os.environ only, ALWAYS lazy (inside functions)
8. no cross-imports between phase1/ phase2/ phase3/

## Key Decisions (locked)
1. Executor = local subprocess — openclaw CLI does not work as specced
2. Fixtures = 5 real git repos in fixtures/syn_001..005/
3. LLM = deepseek-chat — prompt demands raw unified diff, no fences
4. Retry prompt = always includes rejection reason + line count
5. bug_signature = repo:ErrorType:keyword:file
6. Memory dedup = check (repo + bug_signature) before every write
7. Regression = pytest-json-report before/after diff
8. git apply flags = --ignore-whitespace --recount

## Upgrade Queue
v1.1 → Context Builder + RAG                    [DONE — Step 9]
v1.2 → Patch quality fix (5/5 accepted)         [DONE — Step 10]
v1.3 → Thompson Sampling                         [DONE — Step 11]
v1.4 → Claude Code hooks + rules                [DONE — Steps 12-14]
v2.0 → Agent-Y (Reasoning layer / brain)        [NEXT]
v2.1 → Real GitHub webhook integration          [after v2.0]
v2.2 → Local model rotation (Qwen → DeepSeek)   [after v2.1]

## ENFORCEMENT RULE
CLAUDE.md = suggestions (~80% compliance)
.claude/settings.json hooks = requirements (100% enforced)
.claude/rules/*.md = file-type standards (load on demand)
If a rule must ALWAYS run → make it a hook, not a line here.

## SELF-UPDATE RULE
When Claude makes a mistake: say "update CLAUDE.md so this doesn't happen again"
Claude writes the rule. It loads next session. No mistake repeats.
