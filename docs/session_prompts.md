# Agent-X | Session Prompts
# Usage: Open Claude Code → say "step N" → Claude executes that step fully
# Each prompt is self-contained. Claude needs nothing else.
# Last updated: 2026-03-20
#
# STATUS: v1.2 COMPLETE — 2026-03-20
# Steps 0–10 DONE. 187 tests passing. 5/5 accepted. memory.jsonl has 5 entries.
# Next: say "step 11" → Thompson Sampling (LOCKED until memory >= 50 entries)
# Special: say "audit" → run the Agent-X specific audit (see AUDIT section below)

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

---

## STEP 9 — v1.1: Context Builder + RAG Retrieval

```
You are building Agent-X v1.1 — Context Builder upgrade.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.
v1 is COMPLETE. 165 tests pass. Do not break existing tests.

BUILD THIS STEP:

1. phase2/context_builder.py
   - build_context(classifier_result: ClassifierResult, fixture_path: Path) -> str
   - Reads affected file content from fixture (already done in pipeline._build_context — promote to module)
   - Calls get_similar(bug_signature, limit=3) from memory store
   - Formats: file content + 3 past similar fixes (patch + decision) + error summary
   - Returns single context string passed to DeepSeekWorker
   - structlog logging, type hints, Pydantic-safe, __main__ smoke test

2. Update phase2/pipeline.py
   - Replace inline _build_context() + get_similar() call with context_builder.build_context()
   - No other pipeline changes

3. tests/test_context_builder.py
   - Test context includes file content
   - Test context includes similar past fixes when memory has them
   - Test context works when memory is empty
   - Test context works when affected file missing

DONE WHEN:
- pytest tests/ → all pass (165+ tests)
- context_builder.build_context() returns richer context than v1
- docs/progress.md updated: STEP 9 DONE — v1.1
```

---

## STEP 10 — v1.2: Patch Quality Fix (syn_002 / syn_004 / syn_005)

```
You are fixing Agent-X v1.2 — DeepSeek patch quality.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.
v1.1 must be DONE. 180 tests pass. Do not break existing tests.

CONTEXT:
3 of 5 synthetic cases are still rejected every run:
  syn_002 EnvironmentError → DeepSeek omits +++ header line
  syn_004 RuntimeError     → DeepSeek uses wrong file path in diff header
  syn_005 EnvironmentError → DeepSeek generates corrupt / truncated patch

ROOT CAUSE: prompt does not give enough constraints on diff format.

FIX THIS STEP:

1. phase2/patch_gen/worker.py — harden the system prompt:
   - Add explicit unified diff format example in system prompt
   - System prompt must show: exact --- a/file / +++ b/file format
   - System prompt must forbid: any explanation, markdown, fences, partial diffs
   - Retry prompt (attempt > 1) must include: previous rejection reason + exact format reminder

2. phase1/dataset/synthetic.jsonl — verify expected patches for syn_002/004/005:
   - Confirm each expected_patch field is a valid unified diff
   - Fix any malformed expected patches if found

3. tests/test_patch_gen.py — add regression tests:
   - Test system prompt contains "--- a/" format instruction
   - Test retry prompt contains rejection_reason AND format reminder
   - Test validate_patch rejects diff with missing +++ line
   - Test validate_patch rejects diff with wrong path format

DONE WHEN:
- pytest tests/ → all pass (180+ tests)
- python phase2/pipeline.py → at least 4/5 accepted (up from 2/5)
- docs/progress.md updated: STEP 10 DONE — v1.2
```

---

## STEP 11 — v1.3: Thompson Sampling Strategy Engine
# PREREQUISITE: needs 50+ real pipeline runs in memory.jsonl before this step adds value.
# Unlock condition: check memory/memory.jsonl line count. If < 50, do Step 12 first.

```
You are building Agent-X v1.3 — Thompson Sampling strategy engine.
Read CLAUDE.md, docs/progress.md before touching anything.
Step 10 must be DONE. Check: wc -l memory/memory.jsonl — must be >= 50 lines.
If < 50 lines: STOP. Tell user "Thompson needs more data — run the pipeline on real repos first."

WHY THOMPSON NEEDS DATA:
Thompson Sampling starts at Beta(1,1) = uniform random for all arms.
With < 50 runs it has no signal to exploit — it's identical to random.
With 50+ runs per category it learns which fix strategies win and exploits them.

BUILD THIS STEP:

1. phase2/strategy/__init__.py  (empty)

2. phase2/strategy/thompson.py
   - ThompsonSampler: tracks {bug_signature: (alpha, beta)} — one arm per signature
   - sample(bug_signature: str) -> float
     Draw from Beta(alpha, beta). New arms start at Beta(1, 1).
   - update(bug_signature: str, accepted: bool) -> None
     accepted=True  → alpha += 1
     accepted=False → beta  += 1
   - Persists state to memory/thompson_state.json (lazy path, never module-level)
   - load() / save() called internally — never raises (same pattern as memory store)
   - __main__ smoke test: 10 updates, sample, verify state file written

3. Update phase2/pipeline.py
   - Import ThompsonSampler lazily (inside run())
   - Before DeepSeekWorker: score = sampler.sample(bug_signature) → log as exploration_score
   - After DecisionEngine: sampler.update(bug_signature, accepted=(decision=="accepted"))
   - No other pipeline changes

4. tests/test_thompson.py
   - Test alpha increments on accepted
   - Test beta increments on rejected
   - Test new signature starts at Beta(1,1) → alpha=1, beta=1
   - Test sample() returns float in [0.0, 1.0]
   - Test state persists to JSON and reloads correctly
   - Test save/load never raises on bad path (P8 pattern)
   - Test pipeline integration: exploration_score logged after classify

DONE WHEN:
- pytest tests/ → all pass
- memory/thompson_state.json written after pipeline run
- docs/progress.md updated: STEP 11 DONE — v1.3 Thompson
```

---

## STEP 12 — Claude Code Hooks (safety + auto-format + compaction)
# Source: 50 Claude Code Tips — tips 38, 39, 40, 41
# These carry to EVERY future project via ~/.claude/settings.json

```
You are hardening Agent-X's Claude Code session environment.
Read CLAUDE.md, docs/progress.md before touching anything.
Step 11 must be DONE. 206 tests must still pass after this step.

CONTEXT:
CLAUDE.md is advisory (~80% compliance). Hooks are 100% deterministic.
Three hooks to add to .claude/settings.json (create if absent):

BUILD THIS STEP:

1. .claude/settings.json — add all three hooks:

   Hook A — PreToolUse: block destructive bash commands
   Fires BEFORE Claude runs any Bash command.
   Blocks: rm -rf, drop table, truncate, git reset --hard, git push --force
   If matched: print "BLOCKED: destructive command" and exit 2.

   Hook B — PostToolUse: auto-format Python after every file edit
   Fires AFTER Claude edits or writes any .py file.
   Runs: python -m black "$CLAUDE_FILE_PATH" --quiet 2>/dev/null || true
   (|| true so format failures never block Claude)

   Hook C — Notification: re-inject key context after compaction
   Fires on compaction events.
   Prints reminder: current task + modified files + hard rules summary.
   Keeps Claude from losing the thread in long sessions.

   Final .claude/settings.json shape:
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Bash",
           "hooks": [{"type": "command", "command": "...block script..."}]
         }
       ],
       "PostToolUse": [
         {
           "matcher": "Edit|Write",
           "hooks": [{"type": "command", "command": "...black script..."}]
         }
       ],
       "Notification": [
         {
           "matcher": "compact",
           "hooks": [{"type": "command", "command": "...reminder script..."}]
         }
       ]
     }
   }

2. Verify hooks work:
   - Try running: !rm -rf /tmp/test_hook → must be blocked
   - Edit any .py file → black must run silently
   - No existing tests should break

3. Copy .claude/settings.json to ~/.claude/settings.json
   so ALL future projects inherit these hooks automatically.

DONE WHEN:
- .claude/settings.json exists with all 3 hooks
- ~/.claude/settings.json updated (global)
- Destructive command is blocked
- Python auto-format runs silently on edit
- pytest tests/ → still 206 passed
- docs/progress.md updated: STEP 12 DONE
```

---

## STEP 13 — File-type Specific Rules (.claude/rules/)
# Source: 50 Claude Code Tips — tip 31
# Rules that load ONLY when Claude touches relevant files. Keeps CLAUDE.md lean.

```
You are adding file-type specific rules for Agent-X.
Read CLAUDE.md, docs/progress.md before touching anything.
Step 12 must be DONE.

CONTEXT:
.claude/rules/ files load automatically when Claude works on matching file types.
This means Python rules never load when Claude reads docs. Zero token waste.

BUILD THIS STEP:

1. .claude/rules/python.md — loads for all *.py files
   Add paths frontmatter so it only loads for Python:
   ---
   paths:
     - "**/*.py"
   ---
   Content (Agent-X Python standards, extracted from CLAUDE.md):
   - Type hints on every function — no exceptions
   - structlog only — never import logging
   - Pydantic v2 models for all data structures
   - Env vars lazy inside functions — os.environ.get() never at module level
   - pathlib.Path everywhere — no string path concatenation
   - Specific exceptions only — never bare except:
   - Every module has if __name__ == "__main__": smoke test
   - pytest after every file written

2. .claude/rules/tests.md — loads for tests/*.py
   ---
   paths:
     - "tests/**/*.py"
   ---
   Content:
   - Every test class covers: happy path + at least one failure path
   - No mocking of core logic — mock only external calls (API, subprocess)
   - Test function names must describe the behavior being tested
   - Use tmp_path fixture for any file I/O
   - Never hardcode paths — use fixture_path from conftest or tmp_path

3. .claude/rules/docs.md — loads for *.md files
   ---
   paths:
     - "**/*.md"
   ---
   Content:
   - context.md: 80 lines max — index only, never add content directly
   - progress.md: PENDING or DONE only — no diary entries
   - CLAUDE.md: only add a rule if it would prevent a real mistake

DONE WHEN:
- All 3 rule files exist in .claude/rules/
- paths frontmatter correctly set in each
- pytest tests/ → still 206 passed (rules are read-only, no code changes)
- docs/progress.md updated: STEP 13 DONE
```

---

## STEP 14 — CLAUDE.md Litmus Audit + @imports
# Source: 50 Claude Code Tips — tips 29, 32
# Litmus test: "Would Claude make a mistake without this line?" If no → delete it.
# @imports: reference heavy docs instead of embedding them in CLAUDE.md.

```
You are auditing and slimming CLAUDE.md using the litmus test + @imports.
Read CLAUDE.md, docs/progress.md before touching anything.
Step 13 must be DONE.

CONTEXT:
Every unnecessary line in CLAUDE.md dilutes the lines that matter.
There is roughly a 150-200 instruction budget before compliance drops.
@imports let Claude read detail on demand without loading it every session.

BUILD THIS STEP:

1. Litmus test — audit every line in CLAUDE.md:
   For each line ask: "Would Claude make a mistake without this?"
   - YES → keep it
   - NO  → delete it
   - Already enforced by a hook or test → delete it (hook owns it now)
   - Duplicated in .claude/rules/python.md → delete it from CLAUDE.md

2. Replace embedded content with @imports where possible:
   Instead of embedding problem descriptions, write:
   See @docs/problems_and_solutions.md for known bugs and fixes.
   Instead of embedding pipeline details in CLAUDE.md, write:
   Pipeline order → @context.md
   Session prompts → @docs/session_prompts.md

3. Add the self-update habit rule (tip 30):
   ## SELF-UPDATE RULE
   When Claude makes a mistake: say "update CLAUDE.md so this doesn't happen again"
   Claude writes its own rule. It loads next session automatically.

4. Add the hooks-vs-suggestions rule (tip 38):
   ## ENFORCEMENT RULE
   CLAUDE.md = suggestions (80% compliance)
   Hooks (.claude/settings.json) = requirements (100% compliance)
   If a rule must ALWAYS be followed → make it a hook, not a line here.

DONE WHEN:
- CLAUDE.md is shorter than before (lines deleted, not added)
- @imports reference heavy docs instead of embedding
- SELF-UPDATE RULE and ENFORCEMENT RULE added
- pytest tests/ → still 206 passed
- docs/progress.md updated: STEP 14 DONE

COPY TO GLOBAL:
After passing: copy updated CLAUDE.md patterns to ~/.claude/CLAUDE.md
so all future projects start with the litmus-tested habits.
```

---

## AUDIT — Run before starting any new phase

When to use:
- Before starting a new phase (v2.0, v2.1 etc.)
- After a major change to pipeline, memory, or executor
- When something feels broken but tests still pass
- When memory.jsonl starts accumulating and you want a health check

Say "audit" to trigger this.

```
You are auditing Agent-X — an autonomous CI/CD self-healing system built by a solo developer.

Before saying anything, read these files in order:
1. docs/progress.md         → what is built and what passed
2. CLAUDE.md                → hard rules and key decisions
3. context.md               → architecture and pipeline flow
4. docs/problems_and_solutions.md → known bugs and their status
5. phase2/pipeline.py       → the full orchestration logic
6. phase2/patch_gen/worker.py     → DeepSeek prompt + retry logic
7. phase2/patch_gen/sanitiser.py  → diff validation rules
8. phase2/executor/runner.py      → git apply + rollback
9. phase2/executor/regression.py  → before/after pytest comparison
10. phase2/memory/store.py        → append-only JSONL store
11. phase2/context_builder.py     → RAG context assembly
12. memory/memory.jsonl           → actual run history (real data)

DO NOT audit from memory. Read the actual files.

---

WHAT TO AUDIT (in this order):

1. PIPELINE INTEGRITY
   - Does the stage order in pipeline.py match CLAUDE.md exactly?
     Observer → LogParser → RegexClassifier → PreSafetyGate
     → ContextBuilder → DeepSeekWorker → PostSafetyValidation
     → Sanitiser → Executor → RegressionCheck → DecisionEngine → MemoryStore
   - Is the try/finally guarantee for memory write still in place? (Hard Rule 4)
   - Can any exception path skip the memory write?
   - Does rollback() get called on every failure path?

2. DEEPSEEK PROMPT QUALITY
   - Does the system prompt show an exact --- a/ +++ b/ format example?
   - Does the initial prompt specify the exact affected_file path?
   - Does the retry prompt include: rejection_reason + format reminder + affected_file?
   - Is DEEPSEEK_API_KEY read lazily (inside function, never at module level)?

3. SANITISER RULES
   - Does validate_patch() reject: missing +++ line, wrong file path, > 15 lines?
   - Does it check the affected_file path matches the --- a/<path> header?
   - Does strip_markdown_fences() correctly find the first --- line?

4. GIT APPLY SAFETY
   - Does runner.py use: --ignore-whitespace --recount flags?
   - Does rollback() use git checkout -- . (not git reset --hard)?
   - Are temp diff files written with newline="\n" (LF, not CRLF)?

5. MEMORY STORE HEALTH
   - Check memory/memory.jsonl: are all entries valid JSON?
   - Are all required fields present in every entry?
   - Is bug_signature always in format repo:ErrorType:keyword:file?
   - Any entries where decision="abstained" unexpectedly?
   - Are rejected entries building up for the same bug_signature (dedup issue)?

6. REGRESSION CHECK LOGIC
   - Is check_regression() comparing new_failures > before_failures (not total)?
   - Does run_tests() handle fixture with no tests gracefully?
   - Is the JSON report cleaned up after each run?

7. CONTEXT BUILDER (RAG)
   - Does build_context() return 3 sections: error summary, file content, past fixes?
   - Are past fixes capped at 3 entries?
   - Does it handle missing file gracefully (no crash)?
   - Is the token budget respected (error lines capped at 20)?

8. TEST QUALITY CHECK
   For each test file, ask:
   - Are tests verifying real behavior or just that code runs?
   - Are there tests for failure paths (not just happy path)?
   - Any test that would pass even if the module was broken?

9. KNOWN P-BUGS STATUS
   Check docs/problems_and_solutions.md. For each bug marked PENDING:
   - Is it actually still open or was it silently fixed?
   - Does any fixed bug have a regression risk now?

10. COST CHECK
    - How many DeepSeek API calls per pipeline run? (should be 1-3 max per case)
    - Is get_similar() doing a full file scan every call? (JSONL scan — acceptable for < 1000 entries)
    - Any unnecessary reads or writes in the hot path?

---

OUTPUT FORMAT:

### System Health: [GREEN / YELLOW / RED]
One line summary of overall state.

### Critical Issues (fix before next step)
For each: Problem → Why it happens → Impact → Minimal fix

### High Priority Issues
Same format. Fix soon but not blocking.

### Medium / Low Issues
Note but don't act on yet.

### Confirmed Working Correctly
List what you verified is solid. Be specific.

### Suggested Next Action
One thing only. The highest leverage move right now.

---

RULES FOR THIS AUDIT:
- Read the actual code. Do not guess.
- If something looks correct, say so explicitly — don't hedge.
- If you find a real bug, give the minimal fix only (no rewrites).
- Do not suggest anything that requires more than 20 lines of new code.
- Do not suggest features. Audit only what exists.
- Solo developer constraint: every finding must be fixable in one session.
```
