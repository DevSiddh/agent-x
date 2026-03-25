# Agent-X | System Context
# Rule: this file = index only, max 80 lines, NEVER grows beyond this

## Vision
Autonomous software engineer. User gives an idea → system thinks,
designs, builds, tests, fixes its own errors, learns from every run.
CI/CD repair is the proving ground — not the destination.
Full vision → @docs/vision.md

## Current Mission (v3.0 — IN PROGRESS)
Agent-Y (brain) plans goals into Tasks. Agent-X (hands) executes them.
Repair loop proven (v2.3 done, 493 tests). Now building creation mode.
Next: Step X-C0 — Orchestrator + StateManager + write_file()

## Architecture Flow (strict order)
GitHub Actions fails → Observer captures log (last 50 lines)
→ LogParser cleans + extracts error window
→ RegexClassifier identifies error type + confidence
→ PreSafetyGate: confidence < 0.85? STOP → observer mode
→ ContextBuilder: context.md + relevant files + 3 past fixes
→ DeepSeekWorker: generates unified diff patch (raw only, no markdown)
→ PostSafetyValidation: confidence + patch size check
→ Sanitiser: patch > 15 lines? REJECT → retry (max 3, different prompt each)
→ Executor: subprocess git apply + pytest (NO openclaw CLI)
→ RegressionCheck: pytest-json-report before/after, new failures = rollback
→ DecisionEngine: pass=merge | fail=retry | unsure=escalate
→ MemoryStore: append to memory.jsonl (always, even on failure)

## Executor (v1 decision — locked)
NO openclaw sandbox execute/run — those commands do not exist.
Use: subprocess.run(["git", "apply", ...]) + subprocess.run(["pytest", ...])
Fixtures: fixtures/syn_001..005/ — real git repos per synthetic case.

## Failure Taxonomy
DependencyError  : ModuleNotFoundError, pip conflicts, setuptools missing
EnvironmentError : missing env vars, port conflicts, cache bugs
ConfigError      : import order bugs, malformed YAML, missing keys
RuntimeError     : Pydantic errors, assertion failures, type errors
BuildError       : Docker failures, build isolation bugs

## Known Synthetic Cases
syn_001: pkg_resources missing     → DependencyError  → pip install setuptools
syn_002: --no-build-isolation bug  → EnvironmentError → add flag to pip install
syn_003: SQLAlchemy no such table  → ConfigError      → import models before create_all()
syn_004: Pydantic model_ namespace → RuntimeError     → rename field or use alias
syn_005: uvicorn stale __pycache__ → EnvironmentError → pkill + clear cache

## Memory Store Schema
bug_signature format: repo:ErrorType:keyword:affected_file
{
  "run_id", "timestamp", "source", "repo", "failure_category",
  "bug_signature", "confidence_score", "mode", "patch_applied",
  "lines_changed", "model_used", "sandbox_result",
  "regression_introduced", "retries_used", "mttr_seconds",
  "decision", "success_count", "fail_count", "error"
}

## Folder Structure — v2.3 COMPLETE + v3.0 IN PROGRESS (2026-03-25 | 493 tests)
agent-x/
├── phase1/webhook/         server.py, hmac_validator.py       [DONE]
├── phase1/log_fetcher/     fetcher.py, cleaner.py             [DONE]
├── phase1/dataset/         synthetic.jsonl, schema.py         [DONE]
├── phase2/classifier/      regex_pass.py, safety_gate.py, semantic_fallback.py [DONE]
├── phase2/patch_gen/       worker.py, sanitiser.py            [DONE]
├── phase2/executor/        runner.py, regression.py, security_gate.py [DONE]
├── phase2/memory/          store.py, similarity.py, failure_classifier.py [DONE]
├── phase2/tools/           ast_mapper.py, blast_radius.py, pr_creator.py [DONE — D0/D1]
├── phase2/strategy/        thompson.py                        [DONE]
├── phase2/gateway.py       zero-cost direct fixes             [DONE — C2]
├── phase2/pipeline.py      full repair pipeline               [DONE — 493 tests]
├── phase3/                 webhook_worker, runner, log_cleaner_real [DONE — B0-B3]
├── agent_y/                reasoner.py, schemas.py            [DONE — Y-C0]
├── dashboard/              app.py, data.py                    [DONE — E0]
├── fixtures/               syn_001..005/ (real git repos)     [DONE]
├── memory/                 memory.jsonl, thompson_state.json  [LIVE]
├── tests/                  23 test files                      [493 passing]
├── docs/                   progress.md, prompts/, roadmap.md
└── .env.example

## v3.0 New Modules (PENDING — next steps)
├── phase3/state_manager.py     load/save SharedState atomically  [Step X-C0]
├── phase3/orchestrator.py      dumb loop: plan → task → execute  [Step X-C0]
└── phase2/skills/vault.py      Bayesian skill vault              [Step Y-C1]

## Key Reference Docs
problems + solutions → docs/problems_and_solutions.md
build roadmap        → docs/roadmap.md
module details       → docs/modules/<name>.md
env variables        → .env.example
