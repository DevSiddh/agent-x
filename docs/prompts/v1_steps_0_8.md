# Agent-X v1 | Steps 0–8 (DONE — archived)
# All steps here are COMPLETE. Load only for reference.
# Compressed 2026-03-25 — full prompts deleted, summaries only.

---

## STEP 0 — Scaffolding + Fixtures
**Built:** requirements.txt, phase2/ package structure (__init__.py for all subpackages), 5 fixture git repos (syn_001–005) matching synthetic.jsonl patches.
**Done condition:** git apply of each synthetic patch succeeds on its fixture. tests/test_fixtures.py passes.
**Key decisions:** One fixture repo per synthetic case. Each is a real git repo with buggy file committed.
**Status: DONE**

---

## STEP 1 — Spike (Validate Core Loop)
**Built:** spike/run_spike.py — syn_001 → DeepSeek → strip_markdown_fences → git apply → pytest.
**Done condition:** Script runs end-to-end. Spike result reported before Phase 2 build.
**Key decisions:** Must include affected file content in prompt — LLM cannot patch blind.
**Status: DONE**

---

## STEP 2 — fetcher.py Rebuild
**Built:** phase1/log_fetcher/fetcher.py — lazy GITHUB_TOKEN (_get_token()), sorted ZIP namelist, structlog replacing stdlib logging.
**Done condition:** pytest tests/test_fetcher.py all pass. Smoke test runs.
**Key decisions:** P4 (lazy token), P9 (sorted ZIP), P14 (structlog) all fixed here.
**Status: DONE**

---

## STEP 3 — Classifier
**Built:** phase2/classifier/regex_pass.py (ClassifierResult, classify()), phase2/classifier/safety_gate.py (GateDecision, check()).
**Done condition:** All 5 synthetic cases classified correctly. pytest tests/test_classifier.py passes.
**Key decisions:** bug_signature format = repo:ErrorType:keyword:file. Confidence threshold = 0.85. Every score logged (P5).
**Status: DONE**

---

## STEP 4 — PatchGen (Sanitiser + Worker)
**Built:** phase2/patch_gen/sanitiser.py (strip_markdown_fences, validate_patch), phase2/patch_gen/worker.py (generate_patch, retry with different prompt).
**Done condition:** pytest tests/test_patch_gen.py passes. Retry prompt includes rejection_reason (P11).
**Key decisions:** Max 15 diff lines. Max 3 retries. Each retry prompt must differ (P11).
**Status: DONE**

---

## STEP 5 — Executor + Regression
**Built:** phase2/executor/runner.py (apply_patch via subprocess git apply, rollback), phase2/executor/regression.py (run_tests via pytest-json-report, check_regression).
**Done condition:** pytest tests/test_executor.py passes. syn_001 patch applies and fixture tests pass.
**Key decisions:** No openclaw (P1). pathlib.Path + cwd= everywhere (P16). pytest-json-report for before/after diff (P7).
**Status: DONE**

---

## STEP 6 — Memory Store
**Built:** phase2/memory/store.py — MemoryEntry (Pydantic v2), append (never raises, P8), already_fixed (dedup P6), get_similar.
**Done condition:** pytest tests/test_memory.py passes. append never raises even on broken path.
**Key decisions:** bug_signature includes repo prefix (P12). finally-block pattern for P8.
**Status: DONE**

---

## STEP 7 — Pipeline (v1 Complete)
**Built:** phase2/pipeline.py — full stage order wired, try/finally guarantees memory write (P8), all 5 synthetic cases run.
**Done condition:** pytest tests/test_pipeline.py passes. python phase2/pipeline.py runs all 5. memory/memory.jsonl has 5 entries.
**Key decisions:** Hard rules enforced inline: confidence gate, 15-line limit, max 3 retries, always-write finally.
**Status: DONE — v1 COMPLETE**

---

## STEP 8 — Cleanup
**Built:** phase2/logging_config.py (configure_logging(), JSON+ISO timestamps). stdlib logging audit (none found). requirements.txt pinned.
**Done condition:** Full test suite passes. No stdlib logging anywhere. requirements.txt fully pinned.
**Key decisions:** All structlog, no stdlib. Single configure_logging() entry point.
**Status: DONE**
