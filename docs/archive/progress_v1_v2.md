# Agent-X | Archived Progress — v1 through v2.3
# Archived: 2026-03-25
# Contents: All DONE steps from Phase 1 through v2.3 (E0+E1)
# Live progress → docs/progress.md

---

## Phase 1 — Foundation (ALL DONE — 2026-03-20)

| Module | Files | Tests | Key notes |
|--------|-------|-------|-----------|
| Webhook | hmac_validator.py, server.py | 15 | FastAPI, SQLite queue, HMAC |
| Log Fetcher | cleaner.py, fetcher.py | 13 | lazy token, sort, mock HTTP |
| Dataset | synthetic.jsonl, schema.py | PASS | 5 synthetic cases, P13 P14 P15 fixed |

---

## v1 Steps 0–8 (ALL DONE — 2026-03-20)

| Step | What | Tests |
|------|------|-------|
| Step 0 | Scaffolding — fixtures/syn_001..005, all __init__.py, requirements.txt | 26 |
| Step 1 | Spike — DeepSeek loop end-to-end, syn_001 | PASS |
| Step 2 | fetcher.py rebuild — P4 P9 P14 fixed, structlog | 13 |
| Step 3 | Classifier — regex_pass.py, safety_gate.py, 5/5 correct conf=0.99 | 33 |
| Step 4 | PatchGen — worker.py DeepSeek, sanitiser.py, P3 P11 | 19 |
| Step 5 | Executor — runner.py subprocess git apply, regression.py, P1 P7 P16 | 18 |
| Step 6 | Memory — store.py append-never-raises, dedup, get_similar, P6 P8 | 17 |
| Step 7 | Pipeline v1 — all stages wired, try/finally, 5/5 in memory.jsonl | 7 |
| Step 8 | Cleanup — logging_config.py, requirements.txt pinned | 165 total |

Key: Step 1 finding — must include file content in prompt, LLM cannot patch blind.

---

## v1.1–v1.4 Steps 9–14 (ALL DONE — 2026-03-20)

| Step | What | Tests |
|------|------|-------|
| Step 9  | Context Builder + RAG — build_context(), 3-section prompt | 180 total |
| Step 10 | Patch quality — +++ check, path check, --ignore-whitespace, 5/5 accepted | 187 total |
| Step 11 | Thompson Sampling — ThompsonSampler, Beta(α,β), save/load, pipeline wired | 206 total |
| Step 12 | Claude Code Hooks — PreToolUse blocks rm -rf, PostToolUse black, Notification | 206 total |
| Step 13 | File-type Rules — .claude/rules/python.md tests.md docs.md | 206 total |
| Step 14 | CLAUDE.md litmus — 153→73 lines, @imports, ENFORCEMENT RULE, SELF-UPDATE | 206 total |

Step 10 pipeline: 2/5 → 5/5 accepted after +++ header fix + path check + --recount flag.

---

## v2.0 Agent-Y v1 (ALL DONE — 2026-03-20)

| Step | File | Tests | Notes |
|------|------|-------|-------|
| A0 | spike/run_spike_y.py | SPIKE 3/3 | DependencyError, ConfigError, RuntimeError — clean JSON |
| A1 | agent_y/reasoner.py | 27 | ReasonerOutput, reason(), validate_strategy(), _extract_json() |
| A2 | phase2/pipeline.py | 206 | reason() at step 5.5, ReasonerError fallback |
| A3 | — | — | Audit GREEN |

Pipeline: ContextBuilder → Reasoner (deepseek-reasoner) → DeepSeekWorker (deepseek-chat)
5/5 accepted with Agent-Y active.

A4 — TRIGGER-BASED (not built): fires when sensitive code OR API bill >$30/mo.

---

## v2.1 Real GitHub Webhook (ALL DONE — 2026-03-21)

| Step | File | Tests | Notes |
|------|------|-------|-------|
| B0 | spike/run_spike_real.py | SPIKE PASS | real CI log flow validated |
| B1 | phase3/log_cleaner_real.py | PASS | ANSI strip, timestamp remove, failure window |
| B2 | phase3/webhook_worker.py | PASS | dequeue→filter→dedup→fetch→clean→classify→pipeline |
| B3 | phase3/runner.py | 9 | poll_and_process(), KeyboardInterrupt clean exit |

Live results (real GitHub webhook, 2026-03-22): dep_l1/env_l1/cfg_l2/run_l1/run_l2 — all 5 accepted.
Memory: 101+ accepted. C2 gate UNLOCKED. v2.2 gate (20+) UNLOCKED.
Test run: 304 passed, 2 warnings in 75.41s

Dev setup locked: test repo = github.com/DevSiddh/-agent-x-test-repo
Dedup key = (repo, run_id, run_attempt). Log cap = 200KB last. confidence < 0.85 → observer.

---

## v2.1.5 Memory Engine + Pipeline Hardening (ALL DONE — 2026-03-22)

| Step | What | Tests |
|------|------|-------|
| C0 | TF-IDF similarity, MemoryEngine, hybrid ranking, memory reuse bypass | 294 total |
| C1 | run_tests_stable() 3×, Bandit gate, Radon gate, structural escalation | 304 total |
| C2 | Gateway — module_not_found rule, zero LLM cost, wired at step 4.3 | 311 total |

Gateway rule 1: ModuleNotFoundError → appends to requirements.txt. 59x in memory at build time.

---

## v2.1.6 Multi-Language + Audit (ALL DONE — 2026-03-22/23)

| Step | What | Tests |
|------|------|-------|
| C3 | get_runner() by extension (.py→pytest .js→jest .ts→vitest .php→phpunit .java→mvn) | 323 total |
| AUDIT | 13 fixes: AssertionError weight, Thompson penalty, bare except, run_attempt, flaky tracking, Syntax Reflex, Amnesia Protocol | 323 total |
| C3b | JS/PHP/Java/SQL classifier patterns + multi-format log cleaner | 363 total |

AUDIT key fixes: FIX 12 = Syntax Reflex (ast.parse before pytest), FIX 13 = Amnesia Protocol (git clean -fd in rollback).

Step CLS (Embedding Classifier, 2026-03-22):
- semantic_fallback.py: EmbeddingClassifier, build_centroids()
- classify_with_fallback() — Pass 1 regex, Pass 2 Jina embedding when regex < 0.85
- Confidence: min(0.87, S_max + 0.5×(S_max - S_next)), floor 0.55
- Tests: 363 total

P23 Fix — GitHub File Fetch (2026-03-22):
- github_file.py: extract_relative_path() strips /home/runner/work/ prefix → GitHub Contents API
- Tests: 378 total

Step RAG — Triple-Hybrid Semantic Search (2026-03-22):
- Weights: 0.30 TF-IDF + 0.45 Jina-dense + 0.25 Thompson
- Tiers: ≥0.85 bypass → HIGH tag → LOW tag → zero RAG
- Δ = s_dense - s_tfidf logged per entry
- Tests: 350 total (some overlap with CLS run)

---

## v2.2 Context Tools (ALL DONE — 2026-03-24)

| Step | Files | Tests | Notes |
|------|-------|-------|-------|
| D0 | ast_mapper.py, blast_radius.py, web_reader.py, github_search.py, pdf_extractor.py, security_gate.py, regression.py (negative check + shadow type check), runner.py (healthcheck) | 441 total | Web fallback on empty RAG for DepError/EnvError |
| D1 | pr_creator.py (Git Database API, App+PAT auth, always Draft), reasoner.py (diagnosis field), regression.py (complexity delta), store.py (pr_url+issue_url+diagnosis) | 480 total | PR skipped for REPO=="synthetic" |

D0 architecture: negative check (5.8) + security gate (7.5) + shadow type check (8.7) in pipeline.
D1 architecture: branch = agent-x-fixes/{hash}-{run_id}. Structural → Issue with labels.

---

## v2.3 Analytics (ALL DONE — 2026-03-23/24)

| Step | Files | Tests | Notes |
|------|-------|-------|-------|
| E0 | dashboard/data.py, dashboard/app.py | 464 total | Streamlit: run summary, Thompson scores, cost saved, rejection reasons |
| E1 | failure_classifier.py, store.py (rejection_reason field) | 491 total | 6 rejection categories, top_direction signal |

Run dashboard: `python -m streamlit run dashboard/app.py`
Cost model: DeepSeek-chat ~$0.28/1M tokens × 1000 tokens/call = $0.00028/call

---

## Final test count at v2.3 completion: 491 tests passing — 2026-03-24
