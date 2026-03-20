# Agent-X | Build Roadmap
# Last updated: 2026-03-20
# Source: Merged plan from full audit session (Claude + ChatGPT cross-validated)

---

## v1 Done Condition (unchanged)
pipeline.py runs end-to-end on ALL 5 synthetic cases.
All 5 logged in memory/memory.jsonl. That is v1 complete.

---

## Build Philosophy
- One phase at a time. Never start next until current has passing tests.
- Every module gets tests before moving on.
- Problems are fixed AT BUILD TIME, not retrofitted later.
- Run smoke test + pytest after every single file.

---

## STEP 0 — Scaffolding (before any Phase 2 code)
Priority: UNBLOCK EVERYTHING

| Task | File | Fixes |
|------|------|-------|
| Add missing deps | requirements.txt | P13 |
| Create phase2 package structure | phase2/__init__.py + subpackages | P15 |
| Create 5 fixture repos | fixtures/syn_001..005/ | P2 |

Fixture repo spec (each must be a real git repo):
- syn_001: requirements.txt missing setuptools + passing tests
- syn_002: Makefile missing --no-build-isolation + passing tests
- syn_003: app/database.py missing model import + passing tests
- syn_004: app/schemas.py pydantic namespace conflict + passing tests
- syn_005: scripts/restart.sh missing pkill/cache clear + passing tests

Each fixture: git init → create buggy files → git add → git commit
Patch from synthetic.jsonl must apply cleanly to its fixture.

---

## STEP 1 — Spike (validate core loop before full build)
Priority: PROVE IT WORKS

Single throwaway script: spike/run_spike.py
- Load syn_001 from synthetic.jsonl
- Call DeepSeek directly with error log (no classifier yet)
- Print raw LLM response
- Run strip_markdown_fences()
- Count lines
- Apply to syn_001 fixture via subprocess git apply
- Run pytest on fixture
- Print PASS or FAIL with reason

Success = DeepSeek returns a usable patch that applies and passes tests.
Failure = we know exactly where to fix before investing in 8 modules.

DO NOT skip this step. It is the only way to know the system is buildable.

---

## STEP 2 — Phase 1 completion
Priority: CLEAN FOUNDATION

| Task | File | Fixes | Tests |
|------|------|-------|-------|
| Rebuild fetcher.py | phase1/log_fetcher/fetcher.py | P4, P9, P14 | tests/test_fetcher.py |

Changes:
- GITHUB_TOKEN → lazy _get_token() function (P4)
- ZIP files sorted before iteration (P9)
- stdlib logging → structlog (P14)

Phase 1 status after this step: COMPLETE

---

## STEP 3 — Phase 2: Classifier
Priority: FIRST REAL PIPELINE STAGE

| Task | File | Fixes | Tests |
|------|------|-------|-------|
| Regex classifier | phase2/classifier/regex_pass.py | P5 | tests/test_classifier.py |
| Safety gate | phase2/classifier/safety_gate.py | P5 | tests/test_classifier.py |

Rules:
- Classifier returns: category, confidence, matched_pattern, keyword, affected_file
- Log every confidence score (calibrate after 20+ runs, not now)
- Safety gate: confidence < 0.85 → mode=observer, return early
- bug_signature format: repo:ErrorType:keyword:file (P12)

---

## STEP 4 — Phase 2: PatchGen
Priority: LLM INTEGRATION

| Task | File | Fixes | Tests |
|------|------|-------|-------|
| DeepSeek worker | phase2/patch_gen/worker.py | P11 | tests/test_patch_gen.py |
| Sanitiser | phase2/patch_gen/sanitiser.py | P3, P11 | tests/test_patch_gen.py |

Rules:
- System prompt enforces raw unified diff only (P3 layer 1)
- strip_markdown_fences() runs on every response (P3 layer 2)
- Line count check: > 15 lines → reject
- Retry: max 3, each retry includes rejection reason + line count (P11)
- Retry prompt is DIFFERENT from initial prompt (P11)
- Worker reads DEEPSEEK_API_KEY lazily, never at import

---

## STEP 5 — Phase 2: Executor
Priority: PATCH APPLICATION + SAFETY

| Task | File | Fixes | Tests |
|------|------|-------|-------|
| Subprocess executor | phase2/executor/runner.py | P1, P16 | tests/test_executor.py |
| Regression checker | phase2/executor/regression.py | P7 | tests/test_executor.py |

Rules:
- NO openclaw commands. subprocess only (P1)
- git apply → pytest --json-report (P7)
- Regression = new_failures > before_failures (P7)
- All paths use pathlib.Path, cwd= param (P16)
- Rollback = git checkout -- . if regression detected

---

## STEP 6 — Phase 2: Memory Store
Priority: PERSISTENCE + LEARNING

| Task | File | Fixes | Tests |
|------|------|-------|-------|
| Memory store | phase2/memory/store.py | P6, P8, P12 | tests/test_memory.py |

Rules:
- dedup check: (repo + bug_signature) before every write (P6)
- Schema matches context.md Memory Store Schema exactly
- append() wrapped in finally at pipeline level (P8)
- bug_signature always includes repo prefix (P12)

---

## STEP 7 — Phase 2: Pipeline (v1 integration)
Priority: WIRE EVERYTHING + V1 COMPLETE

| Task | File | Fixes | Tests |
|------|------|-------|-------|
| Pipeline orchestrator | phase2/pipeline.py | P8 | tests/test_pipeline.py |

Rules:
- Strict stage order (per CLAUDE.md)
- try/finally guarantees memory write on every run (P8)
- Runs all 5 synthetic cases
- All 5 results in memory.jsonl = v1 DONE

Pipeline stage order (hard):
Observer → LogParser → RegexClassifier → PreSafetyGate
→ ContextBuilder → DeepSeekWorker → PostSafetyValidation
→ Sanitiser → Executor → RegressionCheck
→ DecisionEngine → MemoryStore

---

## STEP 8 — Final cleanup
Priority: POLISH

- Unified structlog config module (P14)
- requirements.txt complete and pinned
- All __init__.py files present
- Windows path audit (P16)
- Run full test suite: pytest tests/ --tb=short

---

## Status Tracker

| Step | Description | Status |
|------|-------------|--------|
| Phase 1: webhook | server.py + hmac_validator.py | DONE |
| Phase 1: log_fetcher | cleaner.py + fetcher.py | DONE |
| Phase 1: dataset | synthetic.jsonl + schema.py | DONE |
| Step 0 | Scaffolding + fixtures | DONE |
| Step 1 | Spike — DeepSeek loop validated | DONE |
| Step 2 | fetcher.py rebuild | DONE |
| Step 3 | Classifier (regex + safety gate) | DONE |
| Step 4 | PatchGen (worker + sanitiser) | DONE |
| Step 5 | Executor (runner + regression) | DONE |
| Step 6 | Memory Store | DONE |
| Step 7 | Pipeline v1 — 5/5 cases | DONE |
| Step 8 | Cleanup (logging_config + pin reqs) | DONE |
| Step 9 | v1.1 Context Builder + RAG | DONE |
| Step 10 | v1.2 Patch quality fix (5/5 accepted) | DONE |
| Step 11 | v1.3 Thompson Sampling | DONE |
| Step 12 | Hooks (auto-format + block destructive + compaction) | DONE |
| Step 13 | .claude/rules/ (Python + tests + docs) | PENDING |
| Step 14 | CLAUDE.md litmus audit + @imports | PENDING |

---

## Key Decisions (locked, do not revisit until v1 ships)
1. Executor → local subprocess, NOT openclaw CLI
2. Fixtures → 5 separate git repos per synthetic case
3. LLM diff → strip_markdown_fences() always runs
4. Token/keys → lazy getters inside functions, never module-level
5. Regression → pytest-json-report before/after comparison
6. Retry → different prompt with failure context, not identical prompt
7. Memory → dedup on (repo + bug_signature) before every write
8. bug_signature → always prefixed with repo name
9. Confidence → log only for v1, calibrate after 20+ real runs
10. Phase 1 cleanup → LAST, after pipeline runs end-to-end
