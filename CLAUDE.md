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
1. Read @NEXT_SESSION.md          → fast path: exact step + file + branch (10 lines)
   If NEXT_SESSION.md is clear → skip to step 3
   If unclear → read @docs/BRIEFING.md for full picture
2. Read that FIX section in docs/prompts/v41_creation_fixes.md
3. Ask user "Ready to start FIX-N?" → wait for confirmation
4. Execute → pytest after every file → update progress.md → STOP
5. Session end → update NEXT_SESSION.md with next step before closing

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

## Current Build Status (2026-03-26) — v4.1 IN PROGRESS
576 tests passing — memory.jsonl 513+ entries — registry.jsonl LIVE — skill_vault.jsonl LIVE
v3 FULLY CLOSED. DeepSeek wired. plan_goal() integrated. registry status fixed.
Next: end-to-end smoke test — drop brief.yaml → idea in → working repo out.
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
- T0 = scaffold task always first — inline scaffold_project(), NOT cookiecutter (no external templates)
- write_file for new files, file_edit for modifications — never write_file on existing files
- ArtifactEntry checksum checked before each task — halt if file changed outside pipeline
- LINE LIMITS (dual-gate, D11, never mix): write_file=50 lines (task cap) | file_edit=15 lines (patch cap)
- ACCEPTANCE TEST: Orchestrator runs pytest (exit code = truth) — never evaluates AcceptanceCriteria cases directly
- CONTENT GENERATION: static AGENT_X_STATIC_PROMPT constant + AcceptanceCriteria + optional Task.hint
  Agent-Y never writes code — only AcceptanceCriteria I/O cases + hint: str = "" when needed
- ROLLBACK (staged files fix): git reset HEAD -- . → git checkout -- . → git clean -fd (NEVER -fdx)
- PROJECT CONTEXT (pulled forward from v3.1 — bake into X-C0):
  Every project gets .agent/context.md committed to GitHub alongside code.
  scaffold_project() creates it. Orchestrator appends after every completed task.
  Format: Goal | Architecture | Key files | Decisions | Known issues | Last task
  When resuming any project: read .agent/context.md FIRST before reading any code file.
  Without this: Agent-XYZ loses all "why" context after 3-10 other projects.
- MULTI-PROJECT STORAGE: persistent WORKSPACE_ROOT (70GB SSD — no ephemeral cloning needed)
  Code pushed to GitHub after every completed task. state.json stays on VPS only.
  registry.jsonl in memory/ = index of all projects (slug, goal, status, created_at)
- VPS CONSTRAINTS (locked — $16/mo DigitalOcean, 2GB RAM + 1GB swap, 1 vCPU, 70GB SSD):
  Sequential only — one project builds at a time (Orchestrator enforces this)
  No local LLM ever — DeepSeek API only (2GB RAM cannot run local models)
  No parallel pytest — 1 vCPU, run single-threaded always
  Use uv for all dependency management — global package cache, no per-project venv bloat
v3.1 → Project memory: goal + architecture + progress state (context.md now in X-C0)
- PROJECT DELETE (v3.2 — Telegram + CLI):
  Trigger: "xyz delete {project_slug}" via Telegram or CLI
  Steps (exact order):
    1. rm -rf WORKSPACE_ROOT/{project_slug}/   ← frees VPS disk immediately
    2. Remove entry from registry.jsonl
    3. Ask user: "Archive or delete GitHub repo?" — default = archive (safe)
    4. memory.jsonl entries = KEEP (learned fixes are signal, not storage)
    5. skill_vault.jsonl = KEEP (learned skills are global, not project-specific)
  Auto-cleanup trigger: WORKSPACE_ROOT hits 80% full → Telegram alert listing
    oldest inactive projects by last_task date → user picks which to delete
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

## GLOBAL CONFIG (portable — works on any machine with this repo)
Full global standards, trigger words, templates → @docs/GLOBAL_CLAUDE.md
Templates (scaffold, brief, blunders, autoresearch, etc.) → docs/
