# Agent-X v1 | Steps 0–8 (DONE — archived)
# All steps here are COMPLETE. Load only for reference.

---

## STEP 0 — Scaffolding + Fixtures

```
You are building Agent-X v1 — autonomous CI/CD self-healing system.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.

BUILD THIS STEP:

1. requirements.txt — add missing: openai>=1.0.0, pydantic>=2.0, pytest-json-report, structlog already there
2. Create package structure (empty __init__.py):
   phase2/__init__.py
   phase2/classifier/__init__.py
   phase2/patch_gen/__init__.py
   phase2/executor/__init__.py
   phase2/memory/__init__.py
3. Create fixtures/ — 5 real git repos, one per synthetic case:
   fixtures/syn_001/ → requirements.txt missing setuptools + minimal pytest test
   fixtures/syn_002/ → Makefile missing --no-build-isolation + minimal pytest test
   fixtures/syn_003/ → app/database.py missing model import before create_all() + test
   fixtures/syn_004/ → app/schemas.py pydantic model_ namespace conflict + test
   fixtures/syn_005/ → scripts/restart.sh missing pkill + cache clear + test
   Each fixture: git init → create buggy files → git add → git commit -m "init buggy state"
   Each fixture: patch from synthetic.jsonl must apply cleanly with git apply

DONE WHEN:
- pip install -r requirements.txt runs clean
- All phase2 __init__.py files exist
- All 5 fixtures are real git repos
- git apply of each synthetic patch works on its fixture
- tests/test_fixtures.py passes — verifies all 5 fixtures accept their patch

Update docs/progress.md after completion.
Only user commits to git.
```

---

## STEP 1 — Spike (Validate Core Loop)

```
You are building Agent-X v1 — autonomous CI/CD self-healing system.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.

BUILD THIS STEP:

Create spike/run_spike.py — throwaway validation script, ~60 lines:
- Load syn_001 from phase1/dataset/synthetic.jsonl
- Call DeepSeek directly (openai client, model=deepseek-chat, base_url=https://api.deepseek.com)
- System prompt: "Return ONLY a unified diff. No markdown. No fences. Start with ---"
- User prompt: error_log from syn_001 + "Fix this. Return unified diff only."
- Print raw LLM response
- Run strip_markdown_fences() on response
- Count diff lines
- Apply to fixtures/syn_001/ via subprocess git apply
- Run pytest on fixtures/syn_001/
- Print PASS or FAIL with exact reason

Requires: DEEPSEEK_API_KEY set in .env
Run it: python spike/run_spike.py

DONE WHEN:
- Script runs without crashing
- DeepSeek returns something
- strip_markdown_fences() extracts a diff
- git apply succeeds OR we see exactly why it fails
- pytest result printed

STOP HERE — report spike result before building any Phase 2 module.
If spike FAILS — report exact failure point. Do not proceed to Step 2.
If spike PASSES — update docs/progress.md, ready for Step 2.
```

---

## STEP 2 — fetcher.py Rebuild

```
You are building Agent-X v1 — autonomous CI/CD self-healing system.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.

BUILD THIS STEP — phase1/log_fetcher/fetcher.py:

Fixes to apply (from problems_and_solutions.md):
- P4: GITHUB_TOKEN must be lazy — _get_token() function called inside fetch_logs(), NOT at module level
- P9: ZIP namelist() must be sorted — sorted(zf.namelist()) before iterating
- P14: Replace stdlib logging with structlog JSON logging

Standards:
- Python 3.11+ type hints on every function
- structlog only, no import logging
- Specific exceptions only, no bare except
- __main__ smoke test with mock (no real GitHub call)

BUILD ALSO: tests/test_fetcher.py
- Test _get_token() raises EnvironmentError when env var missing
- Test _get_token() returns value when env var set
- Test _extract_log_lines() with a real in-memory ZIP
- Test ZIP files are processed in sorted order
- Test extract returns last N lines correctly
- Mock requests.get — no real HTTP calls in tests

DONE WHEN:
- pytest tests/test_fetcher.py → all pass
- smoke test runs: python phase1/log_fetcher/fetcher.py
- docs/progress.md updated
```

---

## STEP 3 — Classifier

```
You are building Agent-X v1 — autonomous CI/CD self-healing system.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.

BUILD THIS STEP:

1. phase2/classifier/regex_pass.py
   - classify(error_lines: list[str], repo: str) -> ClassifierResult
   - ClassifierResult: Pydantic v2 model with:
     category, confidence, matched_pattern, keyword, affected_file, bug_signature
   - bug_signature format: repo:ErrorType:keyword:file (P12)
   - Patterns must cover all 5 failure categories from context.md taxonomy
   - Must correctly classify all 5 synthetic cases (syn_001..005)
   - Confidence: float 0.0-1.0 based on number + strength of matches
   - Log every result with structlog (P5 — track for calibration)

2. phase2/classifier/safety_gate.py
   - check(result: ClassifierResult) -> GateDecision
   - GateDecision: Pydantic v2 model with: passed, mode, reason
   - confidence < 0.85 → passed=False, mode="observer"
   - confidence >= 0.85 → passed=True, mode="repair"
   - __main__ smoke test

3. tests/test_classifier.py
   - Test all 5 synthetic cases classified correctly (category + keyword)
   - Test confidence >= 0.85 for all clear synthetic cases
   - Test safety gate blocks when confidence < 0.85
   - Test safety gate passes when confidence >= 0.85
   - Test bug_signature always contains repo prefix
   - Test ClassifierResult is valid Pydantic model

DONE WHEN:
- pytest tests/test_classifier.py → all pass
- All 5 synthetic cases get correct category
- docs/progress.md updated
```

---

## STEP 4 — PatchGen (Sanitiser + Worker)

```
You are building Agent-X v1 — autonomous CI/CD self-healing system.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.

BUILD THIS STEP:

1. phase2/patch_gen/sanitiser.py
   - strip_markdown_fences(text: str) -> str  (P3)
     Find first line starting with "---", return from there
     Strip ```diff, ```, any code fence prefix
   - count_diff_lines(diff: str) -> int
     Count only lines starting with + or - (excluding +++ ---)
   - validate_patch(diff: str) -> SanitiserResult
     SanitiserResult: Pydantic v2 — passed, diff, line_count, rejection_reason
     Reject if line_count > 15
     Reject if diff doesn't start with ---
   - __main__ smoke test

2. phase2/patch_gen/worker.py
   - generate_patch(error_lines, classifier_result, context, retries=0) -> WorkerResult
   - WorkerResult: Pydantic v2 — diff, raw_response, attempt, model_used
   - DeepSeek call: openai client, DEEPSEEK_API_KEY lazy (never at module level)
   - System prompt: enforce raw unified diff only (P3 layer 1)
   - On retry: prompt MUST include rejection_reason + line_count (P11)
   - Max 3 retries, each with different prompt
   - __main__ smoke test with mock LLM response (no real API call)

3. tests/test_patch_gen.py
   - Test strip_markdown_fences removes fences and keeps diff
   - Test strip_markdown_fences handles already-clean diff
   - Test count_diff_lines counts correctly (ignores +++ ---)
   - Test validate_patch rejects > 15 lines
   - Test validate_patch rejects non-diff text
   - Test validate_patch accepts valid diff
   - Test worker retry uses different prompt (mock LLM)
   - Test worker respects max retries

DONE WHEN:
- pytest tests/test_patch_gen.py → all pass
- docs/progress.md updated
```

---

## STEP 5 — Executor + Regression

```
You are building Agent-X v1 — autonomous CI/CD self-healing system.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.

BUILD THIS STEP:

1. phase2/executor/runner.py
   - apply_patch(patch_diff: str, fixture_path: Path) -> ApplyResult
   - ApplyResult: Pydantic v2 — success, stdout, stderr, error
   - Write diff to temp file, run subprocess git apply (P1 — no openclaw)
   - Use pathlib.Path everywhere, cwd= param (P16)
   - rollback(fixture_path: Path) -> None — git checkout -- .
   - __main__ smoke test using fixtures/syn_001/

2. phase2/executor/regression.py
   - run_tests(fixture_path: Path) -> TestReport
   - TestReport: Pydantic v2 — passed, failed_tests, total, exit_code, raw
   - subprocess pytest --tb=short --json-report --json-report-file=report.json (P7)
   - check_regression(before: TestReport, after: TestReport) -> bool
     True if after.failed_tests > before.failed_tests (P7)
   - __main__ smoke test using fixtures/syn_001/

3. tests/test_executor.py
   - Test apply_patch succeeds on syn_001 fixture with correct diff
   - Test apply_patch fails gracefully with bad diff
   - Test rollback restores file state
   - Test run_tests returns structured report
   - Test check_regression detects new failures
   - Test check_regression passes when failures same or fewer
   - All tests use fixtures/ — real git apply, real pytest

DONE WHEN:
- pytest tests/test_executor.py → all pass
- syn_001 patch applies and its fixture tests pass
- docs/progress.md updated
```

---

## STEP 6 — Memory Store

```
You are building Agent-X v1 — autonomous CI/CD self-healing system.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.

BUILD THIS STEP — phase2/memory/store.py:

- MemoryEntry: Pydantic v2 model matching schema in context.md exactly
  bug_signature format: repo:ErrorType:keyword:file (P12)
- append(entry: MemoryEntry) -> None
  Always writes to memory/memory.jsonl (P8 — never raises, catches all errors)
- already_fixed(bug_signature: str, repo: str) -> bool (P6 — dedup check)
  Returns True if accepted entry exists with same bug_signature + repo
- get_similar(bug_signature: str, limit: int = 3) -> list[MemoryEntry]
  Returns last N entries with same category for context building
- build_default_entry(run_id: str, repo: str) -> MemoryEntry
  Returns entry with decision=abstained, all fields at safe defaults
  Used by pipeline finally block (P8)
- __main__ smoke test — write 3 entries, check dedup, check retrieval

tests/test_memory.py:
- Test append writes valid JSON line
- Test append never raises even if file path broken (P8)
- Test already_fixed returns True for accepted duplicate
- Test already_fixed returns False for new signature
- Test already_fixed returns False for rejected entries
- Test get_similar returns correct entries
- Test MemoryEntry validates against schema

DONE WHEN:
- pytest tests/test_memory.py → all pass
- docs/progress.md updated
```

---

## STEP 7 — Pipeline (v1 Complete)

```
You are building Agent-X v1 — autonomous CI/CD self-healing system.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.

BUILD THIS STEP — phase2/pipeline.py:

run(case_id: str) -> MemoryEntry
- Load case from phase1/dataset/synthetic.jsonl by id
- Execute pipeline in STRICT order:
  1. Observer: load error_lines from case
  2. LogParser: cleaner.clean_and_extract(error_lines)
  3. RegexClassifier: classifier.classify(cleaned, repo="synthetic")
  4. PreSafetyGate: safety_gate.check(result) → if not passed: STOP, mode=observer
  5. ContextBuilder: build minimal context string (error + category + signature)
  6. DeepSeekWorker: worker.generate_patch(cleaned, classifier_result, context)
  7. PostSafetyValidation: sanitiser.validate_patch(diff)
  8. Sanitiser retry loop: if rejected → retry worker (max 3, P11)
  9. Executor: runner.apply_patch(diff, fixture_path)
  10. RegressionCheck: regression.check_regression(before, after)
  11. DecisionEngine: accepted/rejected/escalated/abstained
  12. MemoryStore: ALWAYS in finally block (P8)

- try/finally guarantees memory write on every run (P8)
- Hard rules enforced: confidence gate, 15-line limit, max 3 retries
- Returns MemoryEntry with full run result

run_all_synthetic() -> list[MemoryEntry]
- Runs all 5 synthetic cases: syn_001..005
- Prints summary table: case | category | decision | confidence | lines | result
- All 5 written to memory/memory.jsonl

tests/test_pipeline.py:
- Test single case runs without crash (mock DeepSeek)
- Test observer mode when confidence < 0.85
- Test memory always written even on exception (P8)
- Test all 5 synthetic cases produce MemoryEntry

FINAL RUN (no mocks):
python phase2/pipeline.py
→ must show 5 cases processed
→ memory/memory.jsonl must have 5 entries

DONE WHEN:
- pytest tests/test_pipeline.py → all pass
- python phase2/pipeline.py runs all 5 cases
- memory/memory.jsonl has 5 valid entries
- docs/progress.md updated: v1 COMPLETE

THIS IS THE FINISH LINE.
```

---

## STEP 8 — Cleanup (after v1 ships)

```
You are finishing Agent-X v1 cleanup.
Read CLAUDE.md, docs/progress.md before starting.

DO THESE IN ORDER:

1. Unified structlog config module: phase2/logging_config.py
   - configure_logging() called once at pipeline start
   - JSON format, ISO timestamps
   - All modules import from here

2. Audit all files for stdlib logging — replace with structlog

3. requirements.txt — pin all versions, verify pip install -r requirements.txt clean

4. Run full test suite:
   pytest tests/ --tb=short --cov=phase1 --cov=phase2
   All tests must pass.

5. Update docs/progress.md: STEP 8 DONE — v1 COMPLETE + CLEAN

6. Final git status — tell user what to commit.

DONE WHEN:
- pytest tests/ → all pass, zero failures
- No stdlib logging anywhere
- requirements.txt fully pinned
```
