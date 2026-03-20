# Agent-X | System Context
# Rule: this file = index only, max 80 lines, NEVER grows beyond this

## Mission
Autonomous CI/CD self-healing system.
Detects, classifies, patches, and validates GitHub Actions failures.
Zero regressions. Zero cost. Gets smarter every run.

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

## Folder Structure (v1)
agent-x/
├── phase1/webhook/         server.py, hmac_validator.py       [DONE]
├── phase1/log_fetcher/     fetcher.py (needs rebuild), cleaner.py
├── phase1/dataset/         synthetic.jsonl, schema.py         [DONE]
├── phase2/classifier/      regex_pass.py, safety_gate.py
├── phase2/patch_gen/       worker.py, sanitiser.py
├── phase2/executor/        runner.py, regression.py
├── phase2/memory/          store.py
├── phase2/pipeline.py
├── fixtures/               syn_001..005/ (real git repos)
├── spike/                  run_spike.py (throwaway validator)
├── memory/memory.jsonl
├── tests/
├── docs/roadmap.md         ← full build plan
├── docs/problems_and_solutions.md  ← all bugs + fixes
└── .env.example

## Key Reference Docs
problems + solutions → docs/problems_and_solutions.md
build roadmap        → docs/roadmap.md
module details       → docs/modules/<name>.md

## Env Variables
GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, DEEPSEEK_API_KEY
CONFIDENCE_THRESHOLD=0.85, CHURN_THRESHOLD=15, MAX_RETRIES=3
CI_POLL_TIMEOUT=300, ERROR_WINDOW_LINES=50, WEBHOOK_PORT=8080
