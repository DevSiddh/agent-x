# CLAUDE.md — Agent-X + Agent-Y | Autonomous Software Engineer

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

## VISION (never lose this)
Agent-Y (brain) + Agent-X (hands) = autonomous software engineer.
User gives an idea → Agent-Y thinks, designs, architects, breaks into tasks
→ Agent-X builds, tests, fixes errors, reports back → Agent-Y adapts plan
→ loop until done. CI/CD repair is just the first proving ground.
Full vision → @docs/vision.md

## Current Build Status (2026-03-25) — v3.0 NEXT
491 tests passing — memory.jsonl 406+ entries — thompson_state.json active
v2.1 B0-B3 DONE — v2.2 D0+D1 DONE — v2.3 E0+E1 DONE — Step Y-C0 READY
Full step history → @docs/progress.md

## Pipeline (strict order — do not change)
Observer → LogParser → RegexClassifier → PreSafetyGate
→ Gateway → MemoryReuse → ThompsonSampler.sample()
→ ContextBuilder → Agent-Y Reasoner → NegativeCheck → BaselineTests
→ DeepSeekWorker → Bandit → Radon → SecurityGate
→ Executor → SyntaxReflex → ShadowTypeCheck → RegressionCheck
→ DecisionEngine → ThompsonSampler.update() → AutoPR → MemoryStore

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
v2.0 → Agent-Y reasoning layer                  [DONE — Steps A0-A3]
v2.1 → Real GitHub webhook integration          [DONE — Steps B0-B3]
v2.1.5 → Memory Engine + Pipeline Hardening    [DONE — Steps C0-C2]
v2.1.6 → Multi-language executor + audit fixes  [DONE — Steps C3+AUDIT+C3b]
v2.2   → Context tools + auto-PR               [DONE — Steps D0-D1]
v2.3   → Analytics + failure learning          [DONE — Steps E0-E1]
v3.0 → Plan + Task queue: Y designs, X executes, feedback loop
v3.0.1 → Agent-Y creation mode: schemas + plan_goal() + replan() (Step Y-C0)
v3.0.2 → Agent-X task mode: write_file() + Orchestrator + StateManager (Step X-C0)
v3.0.3 → Bayesian Skill Vault + Best-of-N sampling (Step Y-C1):
         - skill_vault.jsonl: Beta(α,β) per skill, Thompson sampled
         - Best-of-N: n=1 first attempt, n=3 on retry (sequential, stop at first pass)
         - Auto skill generation: retrospective when failed_attempts >= 2 then succeeded
         - Gate: α+β >= 7 before Thompson score trusted (uniform prior until then)
v3.0 Hard Rules (locked 2026-03-25):
- Orchestrator atomic write: state_tmp.json → rename, never direct json.dump to state.json
- Agent-Y called ONLY when: plan empty OR failed_task_streak == 2
- AcceptanceCriteria: min 3 I/O cases (Pydantic enforced) — Happy Path + Edge Case + Error Case
- Agent-X writes test first (parametrize), implementation second
- Replan: inject failed diff + Thompson history — never blind replan
- Replan: surgical sub-tasking only (4 → 4a+4b), never rewrite full plan[]
- global_interfaces: ast_mapper on files_to_touch only, updated after every task
- WORKSPACE_ROOT in .env only — never hardcode paths, never in SharedState
- project_slug in SharedState — Orchestrator resolves full path locally
- resolve_safe_path() must wrap EVERY file write — no exceptions
- T0 = scaffold task always first (cookiecutter)
- write_file for new files, file_edit for modifications — never write_file on existing files
- ArtifactEntry checksum checked before each task — halt if file changed outside pipeline
v3.1 → Project memory: goal + architecture + progress state
v3.2 → Interface layer (locked 2026-03-25):
  - File watcher: drop brief.yaml → /projects/new/ → watchdog triggers Agent-XYZ
  - Streamlit: add current_task_id/total_tasks progress bar (SharedState read)
  - Telegram: inline approve/reject buttons after PR opened
  - PR comments: Agent-XYZ narrates each completed task on the PR
  - GitHub webhook: parse /approve and /fix comments → trigger Orchestrator
  Files: phase3/brief_watcher.py, dashboard/app.py (+10L), telegram bot (+20L),
         pr_creator.py (+15L), webhook/server.py (+20L) — ~95 lines total, one session
  Brief intake folder: /projects/new/
    your-project.yaml   ← required
    *.pdf               ← optional → pdf_extractor.py (already built)
    *.csv / *.json      ← optional → schema extracted → SharedState.data_samples
    *.py / *.js         ← optional → existing code for "improve this" tasks
    *.md                ← optional → research notes, Gemini/ChatGPT outputs, specs, arch docs
  Images: NOT needed until Agent-UI (v4.x) — no visual judgment before then
v4.0 → Fine-tune local model on prompt stack (distillation) [OPTIONAL — cost optimization only, not required for v4.1]
v4.1 → Full autonomous loop: idea in → working repo out

## ENFORCEMENT RULE
CLAUDE.md = suggestions (~80% compliance)
.claude/settings.json hooks = requirements (100% enforced)
.claude/rules/*.md = file-type standards (load on demand)
If a rule must ALWAYS run → make it a hook, not a line here.

## SELF-UPDATE RULE
When Claude makes a mistake: say "update CLAUDE.md so this doesn't happen again"
Claude writes the rule. It loads next session. No mistake repeats.
