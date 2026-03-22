# Agent-X | Progress Tracker
# AUTO-UPDATED by Claude after every completed step + passing tests
# Last updated: 2026-03-22
# Rule: Claude MUST update this file after every step before moving to next

---

## North Star (never lose this)
Autonomous software engineer. Agent-Y (brain) + Agent-X (hands) in a feedback loop.
User gives idea → system thinks, designs, builds, tests, fixes, learns.
CI/CD repair is the proving ground — not the destination.
Full vision → @docs/vision.md

## v1 Goal
pipeline.py runs end-to-end on 5 synthetic cases. All 5 in memory.jsonl.

---

## Overall Status: v2.1.6 IN PROGRESS — 2026-03-22 — RAG + CLS + P23 DONE. Next: E1 → C3b → C4 → D0 → D1 → E0 → E2

---

## PHASE 1 — Foundation

### Webhook (DONE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase1/webhook/hmac_validator.py | DONE | PASS (5/5) | async validate(request), structlog |
| phase1/webhook/server.py | DONE | PASS (15/15) | FastAPI, SQLite queue, HMAC |
| tests/test_webhook.py | DONE | 15 passed | auth, filtering, queue writes, bad JSON |

Last test run: 2026-03-20
```
15 passed in 0.68s
```

---

### Log Fetcher (DONE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase1/log_fetcher/cleaner.py | DONE | PASS | clean + extract_error_window |
| phase1/log_fetcher/fetcher.py | DONE | PASS | P4 P9 P14 fixed |
| tests/test_fetcher.py | DONE | 13 passed | lazy token, sort, mock HTTP |

---

### Dataset (DONE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase1/dataset/synthetic.jsonl | DONE | PASS | 5 synthetic cases |
| phase1/dataset/schema.py | DONE | PASS | validation, all categories covered |
| tests/test_phase1.py | DONE | PASS | schema + cleaner tests |

---

## STEP 0 — Scaffolding (DONE)
| Task | Status | Notes |
|------|--------|-------|
| requirements.txt updated | DONE | added openai>=1.0.0, pydantic>=2.0, pytest-json-report==1.5.0 (fixes P13) |
| phase2/__init__.py | DONE | |
| phase2/classifier/__init__.py | DONE | |
| phase2/patch_gen/__init__.py | DONE | |
| phase2/executor/__init__.py | DONE | |
| phase2/memory/__init__.py | DONE | (fixes P15) |
| fixtures/syn_001/ | DONE | git repo, patch applies cleanly |
| fixtures/syn_002/ | DONE | git repo, patch applies cleanly |
| fixtures/syn_003/ | DONE | git repo, patch applies cleanly |
| fixtures/syn_004/ | DONE | git repo, patch applies cleanly (fixed patch hunk header -10,3→-10,2) |
| fixtures/syn_005/ | DONE | git repo, patch applies cleanly |
| tests/test_fixtures.py | DONE | 26 passed |

Last test run: 2026-03-20
```
26 passed in 0.26s
```

Note: 4 pre-existing failures in test_phase1.py::TestHmacValidator (validate() signature mismatch — not Step 0 scope, not caused by this step)

---

## STEP 1 — Spike (DONE)
| Task | Status | Notes |
|------|--------|-------|
| spike/run_spike.py | DONE | syn_001 → DeepSeek → apply → pytest |
| Spike result | PASS | DeepSeek loop works end-to-end |

Key finding: must include affected file content in prompt — LLM cannot patch blind.

---

## STEP 2 — fetcher.py rebuild (DONE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase1/log_fetcher/fetcher.py | DONE | PASS | P4 P9 P14 fixed, structlog |
| tests/test_fetcher.py | DONE | 13 passed | |

---

## STEP 3 — Classifier (DONE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/classifier/regex_pass.py | DONE | PASS | all 5 cases correct, conf=0.99 |
| phase2/classifier/safety_gate.py | DONE | PASS | repair/observer modes |
| tests/test_classifier.py | DONE | 33 passed | |

---

## STEP 4 — PatchGen (DONE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/patch_gen/worker.py | DONE | PASS | DeepSeek, retry logic, P11 |
| phase2/patch_gen/sanitiser.py | DONE | PASS | P3 strip fences, line count |
| tests/test_patch_gen.py | DONE | 19 passed | |

---

## STEP 5 — Executor (DONE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/executor/runner.py | DONE | PASS | subprocess git apply, rollback, P1 P16 |
| phase2/executor/regression.py | DONE | PASS | pytest-json-report, P7 |
| tests/test_executor.py | DONE | 18 passed | real git apply, real pytest |

---

## STEP 6 — Memory Store (DONE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/memory/store.py | DONE | PASS | append never raises P8, dedup P6, get_similar |
| tests/test_memory.py | DONE | 17 passed | |

---

## STEP 7 — Pipeline (DONE — v1 COMPLETE)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/pipeline.py | DONE | PASS | all stages wired, try/finally P8 |
| tests/test_pipeline.py | DONE | 7 passed | mocked DeepSeek |

Pipeline run results (2026-03-20):
- syn_001 DependencyError  → accepted  (patch applied cleanly)
- syn_002 EnvironmentError → rejected  (DeepSeek omitted +++ header)
- syn_003 ConfigError      → accepted  (patch applied cleanly)
- syn_004 RuntimeError     → rejected  (DeepSeek used wrong file path)
- syn_005 EnvironmentError → rejected  (corrupt patch from DeepSeek)

All 5 logged in memory/memory.jsonl — v1 DONE condition satisfied.

---

## STEP 8 — Cleanup (DONE — 2026-03-20)
| Task | Status | Notes |
|------|--------|-------|
| phase2/logging_config.py | DONE | configure_logging(), JSON+ISO timestamps, wired into pipeline.py |
| stdlib logging audit | DONE | No stdlib logging found anywhere — all structlog |
| requirements.txt pinned | DONE | All versions pinned to exact installed versions |
| Full test suite run | DONE | 165 passed, 0 failures |

Last test run: 2026-03-20
```
165 passed in 33.85s
```

---

## STEP 9 — v1.1: Context Builder + RAG (DONE — 2026-03-20)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/context_builder.py | DONE | PASS | build_context(), 3-section prompt, RAG from memory |
| phase2/pipeline.py | DONE | PASS | wired to build_context(), _build_context() removed |
| tests/test_context_builder.py | DONE | 15 passed | file content, RAG hits, empty memory, missing file |

Last test run: 2026-03-20
```
180 passed in 32.56s
```

---

## v1.1 COMPLETE — 2026-03-20

---

## STEP 10 — v1.2: Patch Quality Fix (DONE — 2026-03-20)
| Task | Status | Notes |
|------|--------|-------|
| Harden SYSTEM_PROMPT in worker.py | DONE | Explicit --- a/ +++ b/ format example, path enforcement |
| Add +++ check to sanitiser.py | DONE | Rejects missing +++ header (syn_002 fix) |
| Add path check to sanitiser.py | DONE | Rejects wrong file path in diff header (syn_004 fix) |
| Add --ignore-whitespace --recount to runner.py | DONE | Handles hunk count mismatch (syn_005 fix) |
| New tests in test_patch_gen.py | DONE | 26 passed (up from 19) |
| Pipeline re-run: 5/5 accepted | DONE | UP FROM 2/5 — all cases now accepted |

Last test run: 2026-03-20
```
187 passed in 33.27s
```

Pipeline results (2026-03-20):
- syn_001 DependencyError  → accepted
- syn_002 EnvironmentError → accepted  (was rejected — +++ header fix)
- syn_003 ConfigError      → accepted
- syn_004 RuntimeError     → accepted  (was rejected — path check fix)
- syn_005 EnvironmentError → accepted  (was rejected — --recount fix)

---

## STEP 14 — CLAUDE.md Litmus Audit + @imports (DONE — 2026-03-20)
| Task | Status | Notes |
|------|--------|-------|
| Litmus test applied | DONE | 153 → 73 lines — deleted coding standards (now in rules/), stale build history, duplicate sections |
| @imports added | DONE | progress.md, session_prompts.md, problems_and_solutions.md referenced not embedded |
| ENFORCEMENT RULE added | DONE | CLAUDE.md=suggestions, hooks=100%, rules=on-demand |
| SELF-UPDATE RULE added | DONE | "update CLAUDE.md so this doesn't happen again" habit |
| Upgrade Queue fixed | DONE | Steps 12-14 marked DONE, v2.0=Agent-Y NEXT |
| Pipeline updated | DONE | Thompson positions added (sample before, update after DeepSeekWorker) |

Last test run: 2026-03-20
```
206 passed in 37.51s
```

---

## STEP 13 — File-type Rules (.claude/rules/) (DONE — 2026-03-20)
| File | Status | Notes |
|------|--------|-------|
| .claude/rules/python.md | DONE | loads for **/*.py — type hints, structlog, pathlib, lazy env vars |
| .claude/rules/tests.md | DONE | loads for tests/**/*.py — coverage, mocking, naming, assertions |
| .claude/rules/docs.md | DONE | loads for **/*.md — context.md 80-line limit, progress.md states |

Last test run: 2026-03-20
```
206 passed in 33.37s
```

Rules load on-demand only — zero token cost when not touching those file types.

---

## STEP 12 — Claude Code Hooks (DONE — 2026-03-20)
| Task | Status | Notes |
|------|--------|-------|
| .claude/settings.json (project) | DONE | 3 hooks: PreToolUse + PostToolUse + Notification |
| ~/.claude/settings.json (global) | DONE | Same hooks merged with existing bypassPermissions |
| black installed | DONE | v26.3.1 — auto-formats .py on every edit |
| Destructive block tested | DONE | rm -rf → BLOCKED, pytest → ALLOWED |
| Full test suite | DONE | 206 passed |

Last test run: 2026-03-20
```
206 passed in 30.82s
```

Hook summary:
- PreToolUse  : blocks rm -rf, drop table, truncate, reset --hard, push --force
- PostToolUse : runs black --quiet on every .py file edit (|| true, never blocks)
- Notification: re-injects project context reminder after every compaction

---

## STEP 11 — v1.3: Thompson Sampling (DONE — 2026-03-20)
| Task | Status | Notes |
|------|--------|-------|
| phase2/strategy/__init__.py | DONE | empty package |
| phase2/strategy/thompson.py | DONE | ThompsonSampler, Beta(alpha,beta), save/load, never raises |
| phase2/pipeline.py | DONE | sample() before DeepSeekWorker, update() after DecisionEngine |
| tests/test_thompson.py | DONE | 19 passed — arm init, update, sample, persistence, integration |

Last test run: 2026-03-20
```
206 passed in 36.10s
```

Pipeline run with Thompson active (2026-03-20):
- thompson.loaded: 2 arms
- DependencyError arm: alpha=7, beta=1 → score=0.99 (high confidence, many wins)
- memory/thompson_state.json written successfully

Unlock condition met: memory.jsonl reached 50 lines before building.

---

## Agent-Y v1 — COMPLETE (2026-03-20)

| Step | File | Status | Tests | Notes |
|------|------|--------|-------|-------|
| A0 | spike/run_spike_y.py | DONE | SPIKE PASS 3/3 | DependencyError, ConfigError, RuntimeError — all JSON valid |
| A1 | agent_y/reasoner.py | DONE | 27 passed | ReasonerOutput, validate_strategy, _filter_files, _extract_json |
| A2 | phase2/pipeline.py | DONE | 206 passed | Reasoner at step 5.5, ReasonerError fallback to raw context |
| A3 | — | DONE | — | Audit GREEN — zero critical issues |
| A4 | — | PENDING | — | Trigger: sensitive code or DeepSeek bill >$30/mo |

Pipeline with Agent-Y (step 5.5):
ContextBuilder → Reasoner (deepseek-reasoner) → DeepSeekWorker (deepseek-chat)

Last test run: 2026-03-20
```
206 passed in 37.51s
```

---

## v2.1.5 — Memory Engine + Pipeline Hardening (IN PROGRESS — C0+C1 DONE)

### v2.1.5 Done Condition
Memory reuse bypass active. Repeated bugs fixed at zero LLM cost. Flaky fixes never reach memory. Bandit rejects unsafe patches. Structural bugs labelled correctly.

### v2.1.5 Status Tracker

| Step | Description | Status |
|------|-------------|--------|
| Step C0 | TF-IDF similarity + hybrid ranking + memory reuse bypass + test_summary | DONE — 2026-03-21 |
| Step C1 | Multi-run verification + Bandit security gate + structural escalation label | DONE — 2026-03-21 |
| Step C2 | Gateway stage — regex direct fixes (data-gated) | PENDING |

### What these steps add
| Upgrade | Solves |
|---------|--------|
| TF-IDF similarity engine | RAG matches by real similarity, not just category |
| Hybrid ranking (sim × Thompson) | Picks most likely to succeed, not just most similar |
| Memory reuse bypass | Skip Agent-Y+X entirely for known bugs — zero LLM cost |
| test_summary in MemoryEntry | Enables weak-success filtering |
| Multi-run verification (3x) | Prevents flaky fixes poisoning memory |
| Bandit security scan | Rejects patches that pass tests but are unsafe |
| Structural escalation label | Correctly identifies architecture-level bugs, stops cleanly |
| Gateway stage | Zero-cost tier for trivial known patterns |

---

## v2.2 Tools — Context Tools for Agent-Y/X (PENDING — after C2)

### v2.2 Tools Done Condition
Agent-Y gets file tree + web docs + PDF summary before planning. Agent-X gets GitHub examples. ContextBuilder uses all 4 tools.

### v2.2 Tools Status Tracker

| Step | Description | Status |
|------|-------------|--------|
| Step D0 | File tree reader + Web reader + GitHub search + PDF summarizer (NotebookLM-style) | PENDING |

### What these tools add
| Tool | What it gives | Who uses it |
|---|---|---|
| File tree reader | Full project layout — prevents file collisions | Agent-Y |
| Web reader | Current API docs — fixes outdated LLM knowledge | Agent-Y |
| GitHub code search | Real-world fix examples for obscure errors | Agent-X |
| PDF summarizer | Structured API/SDK understanding from uploaded docs | Agent-Y |

---

## v2.1.6 — Multi-Language Full Stack (PENDING — after C2)

### v2.1.6 Done Condition
Executor runs correct test runner per language. Classifier recognises JS/PHP/Java/SQL errors. Log cleaner handles all stack trace formats. Visual regressions caught by Playwright.

### v2.1.6 Status Tracker

| Step | Description | Status |
|------|-------------|--------|
| Step C3 | Multi-language executor — jest/vitest/phpunit/junit per file extension | DONE |
| Step AUDIT | 13 fixes: 11 audit bugs + Syntax Reflex (FIX 12) + Amnesia Protocol (FIX 13) | DONE — 2026-03-22 |
| Step C3b | Multi-language classifier + log cleaner patterns (JS/PHP/Java/SQL) | PENDING |
| Step C4 | Playwright visual validation — gated by file extension | PENDING |

### What these steps add
| Upgrade | Solves |
|---------|--------|
| get_runner() by extension | Correct test runner per language |
| JS/PHP/Java/SQL classifier patterns | Non-Python errors correctly classified |
| Multi-format log cleaner | Node.js/PHP/Java stack traces handled |
| Playwright visual check | System no longer blind to UI regressions |
| Radon complexity check (in C1) | Catches architecture risk, not just line count |
| pytesseract OCR (v3.2) | Screenshots/images → text, no second LLM needed |

---

---

## v2.3 — Analytics Layer (PENDING — after D1)

### v2.3 Done Condition
Dashboard shows live pipeline stats. Rejection patterns identified and classified. Cross-repo patterns auto-detected for gateway promotion.

### v2.3 Status Tracker

| Step | Description | Cost | Status |
|------|-------------|------|--------|
| Step E0 | Streamlit dashboard — run summary, Thompson scores, cost saved | $0 | PENDING |
| Step E1 | Failure learning — classify rejection reasons, identify top fix direction | $0 | PENDING |
| Step E2 | Cross-repo pattern detection — auto-generate gateway rule candidates | $0 | PENDING (gate: 3+ repos) |

### What these steps add
| Upgrade | Solves |
|---------|--------|
| Dashboard | Visibility into what's working — no more blind operation |
| Failure learning | Know which pipeline stage to improve (prompt vs context vs logic) |
| Cross-repo detection | Self-improving gateway — more patterns = more zero-cost fixes |

---

### v2.1.6 Done Condition
Executor runs correct test runner per language. JS/PHP/SQL fixes validated. Visual regressions caught by Playwright before accepting frontend fixes.

### v2.1.6 Status Tracker

| Step | Description | Status |
|------|-------------|--------|
| Step C3 | Multi-language executor — jest/vitest/phpunit/junit per file extension | PENDING |
| Step C4 | Visual validation — Playwright + pixelmatch, gated by file extension | PENDING |

### What these steps add
| Upgrade | Solves |
|---------|--------|
| Multi-language executor | MERN, JS, PHP, SQL, MongoDB, all non-Python stacks unlocked |
| get_runner() by extension | Correct test runner auto-detected per language |
| Playwright visual check | System no longer blind to UI regressions |
| Extension gating | Visual check only on .css/.tsx/.jsx/.html — logic files unaffected |

---

## v2.1 — Real GitHub Webhook Integration (COMPLETE — 2026-03-21)

### v2.1 Done Condition
Real GitHub repo CI fails → webhook fires → log fetched → pipeline runs → MemoryEntry written with real repo + real run_id.

### v2.1 Status Tracker

| Step | Description | Status |
|------|-------------|--------|
| Step B0 | Spike — real CI log flow validated | DONE — 2026-03-21 |
| Step B1 | phase3/log_cleaner_real.py + tests | DONE — 2026-03-21 |
| Step B2 | phase3/webhook_worker.py + dedup + fetch | DONE — 2026-03-21 |
| Step B3 | Integration + runner + end-to-end | DONE — 2026-03-21 |

### Dev Environment — FULLY SET UP (2026-03-20)
| Component | Status | Notes |
|-----------|--------|-------|
| Test repo | DONE | github.com/DevSiddh/-agent-x-test-repo |
| CI workflow | DONE | .github/workflows/ci.yml — fails on missing module import |
| Webhook server | DONE | python -m uvicorn phase1.webhook.server:app --port 8000 --env-file .env |
| ngrok tunnel | DONE | nonlogical-unfoaled-omari.ngrok-free.dev (free tier, changes on restart) |
| GitHub webhook | DONE | Workflow runs only, SSL disabled, secret=testsecret123 |
| .env | DONE | GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, DEEPSEEK_API_KEY all set |
| Live event queued | DONE | run_id=23347391009, repo=DevSiddh/-agent-x-test-repo, row_id=1 |

### New Files (phase3/)
| File | Purpose | Status |
|------|---------|--------|
| phase3/__init__.py | empty package | PENDING |
| phase3/log_cleaner_real.py | ANSI strip, timestamp removal, failure window extract | PENDING |
| phase3/webhook_worker.py | dequeue → filter → dedup → fetch → clean → classify → pipeline | PENDING |
| phase3/runner.py | poll loop, structlog every run | PENDING |
| spike/run_spike_real.py | validate real log flow end-to-end | PENDING |

### Key Decisions (locked)
1. phase3/ = entry layer only — never modify phase1/ or phase2/ internals
2. Dedup key = (repo, run_id, run_attempt) — stored in SQLite
3. Filter = workflow_run + conclusion=failure ONLY
4. Log cap = 200KB — take last 200KB (failure near end)
5. run_attempt from webhook payload — always latest
6. confidence < 0.85 on real log → UNKNOWN → observer mode (no guessing)
7. Auto-PR locked until 20+ real accepted fixes confirmed

### Docs created for v2.1
- phase3/context.md — architecture index (80 lines)
- phase3/CLAUDE.md — 10 hard rules for webhook integration
- docs/v21_problems.md — P1-P7 with concrete solutions + P17 P18 P19 (setup bugs)
- docs/v21_roadmap.md — Steps B0-B3
- docs/session_prompts.md — Steps B0 B1 B2 B3 added

### Setup Bugs Discovered + Fixed This Session
| Bug | Fix |
|-----|-----|
| P17 | uvicorn not on PATH → use python -m uvicorn |
| P18 | .env not loaded → always use --env-file .env flag |
| P19 | YAML on: reserved word → use block style not inline |

---

## Live Testing Session — Classifier + Cleaner Fixes (DONE — 2026-03-22)

All 4 patchable categories confirmed working on real GitHub CI logs.

| Fix | File | What changed |
|-----|------|-------------|
| AssertionError weight 0.60 → 0.90 | phase2/classifier/regex_pass.py | Single match now sufficient to pass 0.85 gate |
| `extract_failure_window` n=20 → 40, 75/25 bias | phase3/log_cleaner_real.py | Captures Python traceback before "Process completed" runner line |
| run_l2 test case fixed | test_repo_cases/cases/run_l2/main.py | Explicit raise ensures CI exit code 1; pydantic 2.9.2 was silently passing |

Live results (real GitHub webhook runs):

| Case | Category | Confidence | Decision |
|------|----------|-----------|---------|
| dep_l1 | DependencyError | 0.99 | accepted |
| env_l1 | EnvironmentError | 0.90 | accepted |
| cfg_l2 | ConfigError | 0.99 | accepted |
| run_l1 | RuntimeError | 0.90 | accepted |
| run_l2 | RuntimeError | 0.99 | accepted |

Memory stats: 101+ accepted — C2 gate (≥3 same sig) UNLOCKED — v2.2 gate (20+ accepted) UNLOCKED

Last test run: 2026-03-22
```
304 passed, 2 warnings in 75.41s
```

---

## Step RAG — v2.1 RAG Upgrade: Triple-Hybrid Semantic Search (PENDING — after AUDIT)

### RAG v2.1 Done Condition
TF-IDF + jina-dense + Thompson triple hybrid active. Context injection uses action-tagged
entries. Agent-Y never receives low-quality RAG (score < 0.55). Δ monitoring live.

### RAG v2.1 Status

| Step | Description | Status |
|------|-------------|--------|
| Step RAG | triple hybrid + find_for_rag() + action tags + Δ monitoring | DONE — 2026-03-22 |
| Step RAG-NEG | Negative RAG / Autopsy Protocol | PENDING (gate: 10+ test_failure rejections) |

### Architecture (locked 2026-03-22 — full Gemini review)
| Component | Decision |
|-----------|----------|
| Embedding model | jinaai/jina-embeddings-v2-small-code (code-specific, not all-MiniLM) |
| Thaw template | "{category} ({matched_pattern}) involving {keyword} in file {affected_file}" |
| Weights | 0.30 TF-IDF + 0.45 jina-dense + 0.25 Thompson (fixed until n=500 + Δ signal) |
| TF-IDF | KEPT as exact-match anchor |
| Tier 1 bypass | ≥ 0.85 → skip Agent-Y, auto-apply (find_similar — unchanged) |
| Tier 2 HIGH tag | 0.70–0.84 → [HIGH RELEVANCE: Adapt this pattern] |
| Tier 3 LOW tag | 0.55–0.69 → [LOW RELEVANCE: Loose inspiration only. DO NOT copy directly.] |
| Tier 4 zero RAG | < 0.55 → nothing injected — Agent-Y reasons cold |
| Max injected | 3 entries cap (find_for_rag — new method) |
| Monitoring | Δ = S_dense - S_tfidf logged per scored entry |
| Scale limit | n=500 + repeated Δ>0.40 on failures → manual weight review |

### Parked (post-RAG, data-gated)
| Item | Gate | Target step |
|------|------|-------------|
| Negative RAG (Autopsy) | 10+ test_failure rejections | Step RAG-NEG |
| Web fallback (FinalScore < 0.55 → web search) | D0 ready | Step D0 (added to prompt) |
| AST Graph RAG (cross-file ImportError/TypeError) | 10+ multi-file escalations | Step D0.5 |

---

## Step CLS — Embedding Classifier Fallback (DONE — 2026-03-22)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/classifier/semantic_fallback.py | DONE | PASS | EmbeddingClassifier, build_centroids(), classify() |
| phase2/classifier/regex_pass.py | DONE | PASS | classify_with_fallback() added below classify() |
| phase2/pipeline.py | DONE | PASS | 1 line: classify → classify_with_fallback |
| tests/test_embedding_classifier.py | DONE | 13 passed | model unavailable, no centroids, floor, clear winner, cap, skip |
| tests/test_pipeline.py | DONE | PASS | 2 tests updated to patch classify_with_fallback |

Last test run: 2026-03-22
```
363 passed, 3 warnings in 270.36s
```

Architecture (locked):
- Pass 1: RegexClassifier — always runs, $0, microseconds, 100% deterministic
- Pass 2: EmbeddingClassifier — ONLY when regex confidence < 0.85
- Gate: same 0.85 PreSafetyGate — unchanged
- Model: jinaai/jina-embeddings-v2-small-code — reused from similarity.py, NO second model
- Confidence = min(0.87, S_max + 0.5×(S_max - S_next)) — capped below regex (0.90-0.99)
- Floor 0.55: below → return None → observer mode
- Pipeline: 1 line change only — `classify_with_fallback` replaces `classify`
- Logs: classifier.regex_miss + classifier.semantic_hit on fallback path

---

## P23 Fix — GitHub File Fetch for Runner Paths (DONE — 2026-03-22)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/tools/__init__.py | DONE | — | empty package |
| phase2/tools/github_file.py | DONE | PASS | extract_relative_path(), fetch_file() — never raises |
| phase2/context_builder.py | DONE | PASS | falls back to fetch_file() when local path missing |
| tests/test_github_file.py | DONE | 15 passed | path extraction, 404, no token, network error, CB integration |

Last test run: 2026-03-22
```
378 passed, 3 warnings in 277.54s
```

Problem: affected_file on real GitHub CI runs is `/home/runner/work/{dir}/{dir}/{rel}` — doesn't exist locally.
Fix: `extract_relative_path()` strips runner prefix → `fetch_file()` calls GitHub Contents API.
Repo extracted from first segment of `bug_signature` (`owner/repo:Category:kw:file`).
Local file always takes priority — GitHub API only called when local path is missing.

---

## Step RAG — Triple-Hybrid Semantic RAG (DONE — 2026-03-22)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/memory/similarity.py | DONE | PASS | _thaw(), _get_embedding_model(), _score_entries(), find_for_rag() |
| phase2/context_builder.py | DONE | PASS | uses find_for_rag(), _action_tag(), HIGH/LOW tags in headers |
| tests/test_similarity.py | DONE | PASS | TestThawString + TestFindForRag added, existing tests updated for new weights |
| tests/test_context_builder.py | DONE | PASS | mocks MemoryEngine.find_for_rag, HIGH/LOW tag tests added |
| requirements.txt | DONE | — | sentence-transformers>=2.7.0, einops>=0.6.0 |

Last test run: 2026-03-22
```
350 passed, 3 warnings in 262.58s
```

Architecture (locked):
- Triple hybrid: 0.30 × TF-IDF + 0.45 × Jina-dense + 0.25 × Thompson
- Jina model: jinaai/jina-embeddings-v2-small-code (lazy-loaded, never raises)
- Jina fallback (model unavailable): (0.30/0.55)×TF-IDF + (0.25/0.55)×Thompson
- Tier 1 bypass: ≥ 0.85 → skip Agent-Y (find_similar — unchanged)
- Tier 2 HIGH: 0.70–0.84 → [HIGH RELEVANCE: Adapt this pattern]
- Tier 3 LOW:  0.55–0.69 → [LOW RELEVANCE: Loose inspiration only. DO NOT copy directly.]
- Tier 4 zero RAG: < 0.55 → nothing injected
- Δ = s_dense - s_tfidf logged per scored entry (monitoring signal)
- find_similar() return format UNCHANGED — pipeline.py untouched

---

## Step AUDIT — 13 Codebase Fixes (DONE — 2026-03-22)
| Fix | File | What changed |
|-----|------|-------------|
| FIX 1 | phase2/classifier/regex_pass.py | AssertionError weight 0.09 → 0.70 |
| FIX 2 | phase2/strategy/thompson.py + pipeline.py + schema.py | penalty=5 for structural, "structural" in DECISIONS |
| FIX 3 | phase2/memory/similarity.py | bare except → except Exception as exc with log.error |
| FIX 4 | phase1/webhook/server.py + phase3/webhook_worker.py | run_attempt column added to schema + SELECT |
| FIX 5 | phase2/executor/regression.py | last_passing tracked separately — guaranteed non-None |
| FIX 6 | phase3/webhook_worker.py | lazy _ensure_dedup_db() — no module-level init |
| FIX 7 | phase1/dataset/schema.py + synthetic.jsonl + tests | bug_signature 4-part format enforced |
| FIX 8 | phase2/executor/regression.py | unknown report format logged as warning |
| FIX 9 | phase2/pipeline.py | memory reuse double-run bug fixed |
| FIX 10 | phase2/patch_gen/worker.py | exponential backoff jitter added between retries |
| FIX 11 | phase2/gateway.py | depth-limited rglob (max_depth=3) in all fix functions |
| FIX 12 | phase2/executor/runner.py + pipeline.py | Syntax Reflex — ast.parse() before pytest for .py files |
| FIX 13 | phase2/executor/runner.py | Amnesia Protocol — git clean -fd added to rollback() |

Last test run: 2026-03-22
```
323 passed, 3 warnings in 250.10s
```

---

## Step C3 — Multi-Language Executor (DONE — 2026-03-22)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/executor/runner.py | DONE | PASS | get_runner() — extension → command map |
| phase2/executor/regression.py | DONE | PASS | parse_report() Jest+pytest, run_tests(affected_file) |
| fixtures/syn_js_001/ | DONE | — | app.js (buggy), app.test.js, package.json |
| tests/test_multilang_executor.py | DONE | 12 passed | runner selection, report parsing, JS fixture |

Last test run: 2026-03-22
```
323 passed, 3 warnings in 105.72s
```

Runner map: .py→pytest .js→jest .ts→vitest .php→phpunit .java→mvn — fallback pytest for unknown.
JS fixture test skips gracefully if Node not installed.

---

## Step C2 — Gateway Stage (DONE — 2026-03-22)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/gateway.py | DONE | PASS | GatewayResult, module_not_found rule, check() |
| phase2/pipeline.py | DONE | PASS | Gateway wired at step 4.3, before memory reuse |
| tests/test_gateway.py | DONE | 7 passed | match, append, miss, pipeline hit + fallthrough |

Last test run: 2026-03-22
```
311 passed, 2 warnings in 103.29s
```

Gateway rule 1 — module_not_found (59x in memory):
- Matches: ModuleNotFoundError: No module named X
- Fix: appends X to requirements.txt
- Pipeline: accepted with model_used="gateway", zero LLM cost

v2.1.5 COMPLETE — C0 + C1 + C2 all done.

---

## Step C1 — Pipeline Hardening (DONE — 2026-03-21)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/executor/regression.py | DONE | PASS | run_tests_stable(), note="flaky" field |
| phase2/pipeline.py | DONE | PASS | Bandit gate, Radon gate, structural escalation, run_tests_stable wired |
| tests/test_hardening.py | DONE | 10 passed | flaky detection, bandit gate, structural escalation |

Last test run: 2026-03-21
```
304 passed, 2 warnings in 298.58s
```

---

## Step C0 — Memory Engine (DONE — 2026-03-21)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase2/memory/store.py | DONE | PASS | test_summary field added |
| phase2/memory/similarity.py | DONE | PASS | MemoryEngine, TF-IDF + hybrid ranking, threshold=0.85 |
| phase2/pipeline.py | DONE | PASS | Memory reuse bypass wired (4.5 stage), test_summary populated |
| tests/test_similarity.py | DONE | 11 passed | find_similar, hybrid ranking, reuse bypass integration |

Last test run: 2026-03-21
```
294 passed, 1 warning in 284.97s
```

---

## Step B3 — v2.1 Integration + Runner (DONE — 2026-03-21)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| phase3/runner.py | DONE | PASS | poll_and_process(), KeyboardInterrupt clean exit, structlog |
| tests/test_v21_integration.py | DONE | 9 passed | queue→memory, dedup, non-failure filter, observer mode, queue row marked done |

Last test run: 2026-03-21
```
283 passed, 1 warning in 277.25s
```

---

## Test Run History
| Date | Command | Result |
|------|---------|--------|
| 2026-03-20 | pytest tests/test_webhook.py | 15 passed in 0.68s |
| 2026-03-20 | pytest tests/test_phase1.py | (run pending after cleaner check) |
| 2026-03-20 | pytest tests/test_fixtures.py | 26 passed in 0.26s |
| 2026-03-20 | python spike/run_spike.py | SPIKE PASS — end-to-end loop confirmed |
| 2026-03-20 | pytest tests/test_fetcher.py | 13 passed in 0.31s |

---

## Bugs Fixed So Far
| Bug | Fix | In |
|-----|-----|----|
| P10 DB_PATH module-level | temp DB override in tests | test_webhook.py |
| P1 OpenClaw CLI | subprocess decision locked | CLAUDE.md + roadmap |

---

## Bugs Still Open
P2 P3 P4 P5 P6 P7 P8 P9 P11 P12 P13 P14 P15 P16
See docs/problems_and_solutions.md for full detail.

---

## AGENT-Y v1 — Reasoning Layer

### Overall Status: PENDING — not started

---

### Step A0 — Spike (DONE — 2026-03-20)
| Task | Status | Notes |
|------|--------|-------|
| spike/run_spike_y.py | DONE | 3 categories: DependencyError, ConfigError, RuntimeError |
| Spike result | PASS | 3/3 cases — clean JSON, no fences, all 5 keys, correct files |

Key findings:
- DeepSeek returns clean JSON without fences when system prompt says "start with {"
- Strategy is specific and correct for each error category
- files_to_change correctly identifies affected file in all 3 cases
- No fence stripping needed (though _extract_json() handles it defensively)

---

### Step A1 — Reasoner Module (DONE — 2026-03-20)
| File | Status | Tests | Notes |
|------|--------|-------|-------|
| agent_y/__init__.py | DONE | — | empty package |
| agent_y/reasoner.py | DONE | PASS | ReasonerOutput, reason(), validate_strategy(), _filter_files(), _extract_json() |
| tests/test_reasoner.py | DONE | 27 passed | happy path, retry, ReasonerError, strategy mismatch, AST check on confidence |

Last test run: 2026-03-20
```
233 passed, 1 warning in 45.26s
```

---

### Step A2 — Wire into Pipeline (DONE — 2026-03-20)
| Task | Status | Notes |
|------|--------|-------|
| phase2/pipeline.py updated | DONE | reason() slotted at step 5.5 between ContextBuilder and DeepSeekWorker |
| ReasonerError fallback tested | DONE | mock raises → pipeline continues with raw context |
| tests/test_pipeline.py updated | DONE | 2 new tests: enriched context + fallback path |
| Pipeline re-run: 5/5 accepted | DONE | reasoner.ok logged for all 5 cases |

Last test run: 2026-03-20
```
235 passed, 1 warning in 36.90s
```

Pipeline run (2026-03-20):
- syn_001 DependencyError  → accepted  (reasoner.ok — strategy: install setuptools)
- syn_002 EnvironmentError → accepted  (reasoner.ok — strategy: add --no-build-isolation)
- syn_003 ConfigError      → accepted  (reasoner.ok — strategy: import models before create_all)
- syn_004 RuntimeError     → accepted  (reasoner.ok — strategy: add model_config namespace fix)
- syn_005 EnvironmentError → accepted  (reasoner.ok — strategy: clear __pycache__ on restart)

### Overall Status: Agent-Y v1 COMPLETE — 2026-03-20

---

### Step A4 — Prompt Loader + Local Model (PENDING — trigger-based)
| Task | Status | Notes |
|------|--------|-------|
| agent_y/prompt_loader.py | PENDING | triggered when: sensitive code or bill >$30 |
| agent_y/reasoner.py updated | PENDING | REASONER_MODEL env var switch |
| tests/test_prompt_loader.py | PENDING | |

Trigger: real prod repos with sensitive code OR monthly API bill exceeds $30/month.
Say "step A4" when trigger fires.

---

### Step A3 — Autoresearch Gate (DONE — 2026-03-20)
| Task | Status | Notes |
|------|--------|-------|
| 20+ pipeline runs logged | DONE | 4 runs × 5 cases = 20 cases with Agent-Y active |
| Check 4 evaluated | DONE | 20/20 accepted — no regression from adding Reasoner |
| v1.1 gate decision | DONE | 4/4 checks pass for 20 consecutive runs → v1.1 UNLOCKED |

Autoresearch results:
- Check 1: 20/20 — clean JSON, no fence stripping needed (deepseek-reasoner)
- Check 2: 20/20 — validate_strategy() passed every run (zero ReasonerError fallbacks)
- Check 3: 20/20 — files_to_change correct and capped (single-file fixes all cases)
- Check 4: 20/20 — 100% acceptance rate maintained post-Agent-Y (baseline was 5/5)

v1.1 unlocked: local model (Ollama + Qwen2.5-7B) for Agent-Y reasoning
