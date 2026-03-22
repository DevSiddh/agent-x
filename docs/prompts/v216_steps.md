# Agent-X v2.1.6 | Steps C3–C4 + C3b (PENDING — after C2)
# Multi-Language Executor + Classifier + Visual Validation

---

## STEP AUDIT — Audit Bug Fixes (run before C3b)
# Prerequisite: C3 DONE.
# Source: Full codebase audit 2026-03-22 — 30 issues found, fix critical+high first.

```
You are fixing critical and high-severity bugs found in the 2026-03-22 audit.
Read CLAUDE.md, docs/progress.md before touching anything.
Do NOT add features. Only fix the listed bugs. Run full test suite after each fix.

FIX 1 — regex_pass.py — fix assertion_error weights (two patterns, different weights)
File: phase2/classifier/regex_pass.py
Line 55: _Pattern(r"AssertionError") → weight must be 0.90 (exact exception class, high fidelity)
Line 56: _Pattern(r"assert.*failed|assertion failed") → weight must be 0.70 (noisy signal, NOT 0.90)
Why 0.70 not 0.90: enterprise logs contain "assertion failed" in passing test output.
0.70 = corroborating signal only — cannot trigger pipeline alone (gate is 0.85).
0.90 = execution trigger — fires on noisy logs = false positives on real repos.
Change line 56 from 0.09 → 0.70. Run tests.

FIX 2 — schema.py + pipeline.py — structural decision + Thompson heavy penalty
File 1: phase1/dataset/schema.py line 18
  Add "structural" to DECISIONS tuple:
  DECISIONS = ("accepted", "rejected", "escalated", "abstained", "structural")

File 2: phase2/pipeline.py — Thompson update on structural
  Current: rejected → Thompson.update(arm, reward=0) → β+1
  Add:     structural → Thompson.update(arm, reward=0, penalty=5) → β+5
  Why: structural is a hard wall, not a bad guess. β+5 means next time the same
  bug signature appears → system instantly escalates, zero API cost.
  If ThompsonSampler.update() doesn't support penalty param → add it:
    def update(self, arm: str, reward: int, penalty: int = 1) -> None:
        self.arms[arm] = (alpha + reward, beta + penalty)

  Note: DO NOT open GitHub issues here — that is Step D1's job.
  Here: only schema fix + Thompson penalty. Keep scope tight.
Run tests.

FIX 3 — similarity.py — log before swallowing exceptions
File: phase2/memory/similarity.py lines 76, 136
Every bare `except Exception:` must log before returning.
Pattern: log.error("similarity.failed", error=str(e)) before return []
Run tests.

FIX 4 — webhook_worker.py — run_attempt hardcoded to 1
File: phase3/webhook_worker.py line 202
Extract run_attempt from the webhook payload stored in queue row.
Update queue schema if needed to store run_attempt at enqueue time.
Run tests.

FIX 5 — regression.py — flaky detection returns wrong result
File: phase2/executor/regression.py lines 135-152
run_tests_stable() must return the LAST PASSING report, not the last run.
Fix the return logic: track which run passed all 3, return that report.
Run tests.

FIX 6 — webhook_worker.py — init_dedup_db at module level
File: phase3/webhook_worker.py line 72
Move init_dedup_db() call inside process_next() or a lazy initializer.
Pattern: call once on first use, not at import time.
Run tests.

FIX 7 — schema.py — bug_signature format mismatch
File: phase1/dataset/schema.py line 44
Validation expects 3-part format. Real entries are 4-part (repo:ErrorType:keyword:file).
Update validation to expect 4 parts. Run tests.

FIX 8 — regression.py — unrecognized runner silently passes
File: phase2/executor/regression.py lines 27-65
If runner is not pytest or jest, parse_report currently returns ([], 0) silently.
Add: log.warning("regression.unknown_runner", runner=runner) + raise ValueError or return clearly.
Run tests.

FIX 9 — pipeline.py — duplicate test run in memory reuse path
File: phase2/pipeline.py line 267
run_tests() called twice. Store result first call, pass stored result to check_regression.
Run tests.

FIX 10 — worker.py — add jitter to DeepSeek retry backoff
File: phase2/patch_gen/worker.py
Current retry loop has no jitter — concurrent workers all retry at same second → thundering herd.
Add: wait = min(2 ** attempt + random.uniform(0, 1), 60)
import random at top of file. Run tests.

FIX 11 — gateway.py — rglob no depth limit on real repos
File: phase2/gateway.py line 92
Add max_depth=3 to rglob equivalent. Use os.walk with level counter or pathlib depth check.
Run tests.

FIX 12 — runner.py — no syntax check before pytest (Syntax Reflex)
File: phase2/executor/runner.py
After apply_patch() succeeds but BEFORE running pytest, add ast.parse() check for .py files only.
Pattern:
  if Path(affected_file).suffix == ".py":
      try:
          ast.parse(patched_file_path.read_text())
      except SyntaxError as e:
          rollback(fixture_path)
          return ApplyResult(success=False, error=f"SyntaxError line {e.lineno}: {e.msg}")
      # only then → run pytest
Cost: $0, ~1ms. Saves running 323 tests for a dumb indentation error.
import ast at top of file. Run tests.

FIX 13 — runner.py — rollback() leaves untracked files (Amnesia Protocol)
File: phase2/executor/runner.py line 104
Current rollback() uses `git checkout -- .` — restores tracked files only.
If a failed patch creates new untracked files, they survive into the next retry.
Add `git clean -fd` after `git checkout -- .`:
  subprocess.run(["git", "checkout", "--", "."], cwd=fixture_path, ...)
  subprocess.run(["git", "clean", "-fd"], cwd=fixture_path, capture_output=True)
Every retry now runs against true HEAD — no Frankenstein state from previous attempt.
Run tests.

DONE WHEN:
- pytest tests/ → all pass (zero regressions, count must not decrease)
- All 13 fixes applied
- docs/progress.md updated: Step AUDIT DONE
```

---

## STEP C3 — v2.1.6: Multi-Language Executor
# Prerequisite: Step C2 DONE.

```
You are building Agent-X v2.1.6 — multi-language executor upgrade.
Read CLAUDE.md, docs/progress.md before touching anything.
Step C2 must be DONE. Do not break existing tests.

CONTEXT:
Current executor only runs pytest (Python only).
One upgrade — detect language from file extension → run correct test runner.
This unlocks MERN, JS, PHP, SQL, MongoDB, all non-Python stacks.

RUNNER MAP (implement exactly):
.py   → ["python", "-m", "pytest", "--tb=short", "--json-report", "--json-report-file=report.json"]
.js   → ["npx", "jest", "--json", "--outputFile=report.json"]
.ts   → ["npx", "vitest", "run", "--reporter=json"]
.php  → ["phpunit", "--log-json", "report.json"]
.java → ["mvn", "test"]
default → pytest (fallback)

BUILD THIS STEP:

1. Update phase2/executor/runner.py
   - get_runner(affected_file: str) -> list[str]
     Detect extension from Path(affected_file).suffix
     Return correct runner command list from RUNNER_MAP
     Fallback to pytest if extension not recognised
   - Update apply_patch() to use get_runner() for test execution
   - structlog logs which runner was selected: log.info("executor.runner", lang=ext)

2. Update phase2/executor/regression.py
   - parse_report(report_path: Path, runner: str) -> TestReport
     Jest JSON format differs from pytest JSON — handle both
     Normalise to same TestReport schema regardless of runner
   - __main__ smoke test

3. Add multi-language fixtures (minimum 1 JS fixture):
   fixtures/syn_js_001/ — simple Node.js project with a bug + jest test
   git init → buggy file → jest test → git commit

4. tests/test_multilang_executor.py
   - Test get_runner returns pytest for .py files
   - Test get_runner returns jest command for .js files
   - Test get_runner falls back to pytest for unknown extension
   - Test parse_report handles jest JSON format
   - Test parse_report handles pytest JSON format
   - Test apply_patch on syn_js_001 fixture with jest runner

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- JS fixture fix applies and jest runs cleanly
- docs/progress.md updated: Step C3 DONE — v2.1.6
```

---

## STEP C3b — v2.1.6: Multi-Language Classifier + Log Cleaner Patterns
# Prerequisite: Step C3 (multi-language executor) DONE.

```
You are adding multi-language support to classifier and log cleaner.
Read CLAUDE.md, docs/progress.md before touching anything.
Step C3 must be DONE. Do not break existing tests.

CONTEXT:
Classifier and log cleaner currently handle Python/GitHub Actions format only.
Adding JS/PHP/Java/SQL patterns unlocks full multi-language support end-to-end.

BUILD THIS STEP:

1. phase2/classifier/regex_pass.py — add language patterns

   JS/Node patterns:
   - "Cannot find module" → DependencyError
   - "ReferenceError: .* is not defined" → RuntimeError
   - "SyntaxError: Unexpected token" → SyntaxError
   - "TypeError: .* is not a function" → RuntimeError
   - "ECONNREFUSED" → EnvironmentError

   PHP patterns:
   - "Fatal error: Class .* not found" → DependencyError
   - "Parse error: syntax error" → SyntaxError
   - "Warning: .* expects parameter" → RuntimeError

   Java patterns:
   - "ClassNotFoundException" → DependencyError
   - "NullPointerException" → RuntimeError
   - "at .*\(.*\.java:\d+\)" → stack trace marker

   SQL patterns:
   - "Table .* doesn't exist" → ConfigError
   - "Column .* not found" → ConfigError
   - "Access denied for user" → EnvironmentError

2. phase3/log_cleaner_real.py — add stack trace formats

   Node.js stack trace format:
   - "at Object.<anonymous> (file.js:line:col)"
   - npm/yarn error output patterns

   PHP error log format:
   - "[date] PHP Fatal error: ... in file.php on line N"

   Java stack trace format:
   - "at com.example.Class.method(File.java:42)"
   - "Caused by: java.lang.*"

3. tests/test_multilang_classifier.py
   - Test JS errors classified correctly (5 cases)
   - Test PHP errors classified correctly (3 cases)
   - Test Java errors classified correctly (3 cases)
   - Test SQL errors classified correctly (3 cases)
   - Test Python errors still classified correctly (regression)

3. phase2/executor/runner.py — replace extension map with manifest detection
   REPLACE get_runner(affected_file) with detect_runner(fixture_path, affected_file):
   - Walk UP from affected_file.parent to fixture_path (repo root)
   - First manifest found = execution_root + runner command
   - Manifest priority: package.json → pyproject.toml/pytest.ini → tox.ini → pom.xml → build.gradle → Makefile
   - package.json: parse scripts.test, check yarn.lock for package manager
   - Kill switch: if no manifest found → raise TestRunnerDetectionError
     pipeline catches → decision="abstained", reason="no test runner detected"
   - NEVER silent fallback to pytest — explicit failure > wrong runner

   Signature change (breaking — update all callers):
     OLD: get_runner(affected_file: str) -> list[str]
     NEW: detect_runner(fixture_path: str, affected_file: str) -> tuple[list[str], Path]
   Update apply_patch() to use execution_root as subprocess cwd (not fixture_path)

4. phase2/strategy/thompson.py — arm migration + ecosystem naming
   BREAKING CHANGE: rename all existing arms to Category_Ecosystem format
   Migration function run once on startup if old format detected:
   ```python
   def _migrate_arms(arms: dict) -> dict:
       # if arm has no underscore → add _Python suffix
       return {
           (k if "_" in k else f"{k}_Python"): v
           for k, v in arms.items()
       }
   ```
   Update sample() and update() to accept arm key as "{Category}_{Ecosystem}"
   Classifier must pass ecosystem to pipeline → pipeline passes to Thompson
   Ecosystem detection: Path(affected_file).suffix → _ECOSYSTEM_MAP
   _ECOSYSTEM_MAP = {".py": "Python", ".js": "Node", ".ts": "Node",
                     ".php": "PHP", ".java": "Java", default: "Python"}

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- All 4 new language categories classified correctly
- thompson_state.json arms all have Category_Ecosystem format
- docs/progress.md updated: Step C3b DONE
```

---

## STEP C4 — v2.1.6: Visual Validation Layer (Playwright)
# Prerequisite: Step C3 DONE.
# Data gate: only build when frontend fixes appear in memory.jsonl

```
You are building Agent-X v2.1.6 — visual validation layer.
Read CLAUDE.md, docs/progress.md before touching anything.
Step C3 must be DONE.

PREREQUISITE CHECK:
Check memory.jsonl — does any accepted entry have affected_file ending in
.css/.tsx/.jsx/.html/.vue? If none → STOP. No visual fixes in memory yet.
Wait until frontend fixes accumulate before building this.

CONTEXT:
System is blind to visual output. Logic tests pass but UI can be broken.
Playwright headless + pixelmatch catches visual regressions.
CRITICAL: only runs when affected_file is a visual file — never on logic files.

VISUAL FILE EXTENSIONS (gate trigger):
.css, .scss, .sass, .html, .tsx, .jsx, .vue

BUILD THIS STEP:

1. phase2/executor/visual_validator.py — NEW FILE
   - VISUAL_EXTENSIONS: set = {".css", ".scss", ".sass", ".html", ".tsx", ".jsx", ".vue"}
   - is_visual_fix(affected_file: str) -> bool
     Return True if Path(affected_file).suffix in VISUAL_EXTENSIONS
   - capture_screenshot(fixture_path: Path, output_path: Path) -> bool
     Run: playwright screenshot --browser chromium {index_file} {output_path}
     Return True if screenshot captured, False if failed (never raises)
   - compare_screenshots(before: Path, after: Path, threshold: float = 0.02) -> VisualResult
     VisualResult: Pydantic v2 — passed: bool, diff_ratio: float, reason: str
     Use pixelmatch or looks-same for pixel diff
     passed=True if diff_ratio < threshold
   - structlog on every check, type hints, __main__ smoke test
   - Never raises — wrap everything in try/except, return VisualResult(passed=True) if tool missing

2. Update phase2/pipeline.py — add visual check after executor.apply_patch()
   ```
   if visual_validator.is_visual_fix(classifier_result.affected_file):
       before_shot = capture_screenshot(fixture_path, before_path)
       apply_patch(...)
       after_shot = capture_screenshot(fixture_path, after_path)
       visual_result = compare_screenshots(before_path, after_path)
       if not visual_result.passed:
           log.warning("visual.regression", diff=visual_result.diff_ratio)
           runner.rollback(fixture_path)
           decision = "rejected"
   ```

3. tests/test_visual_validator.py
   - Test is_visual_fix returns True for .css/.tsx/.jsx/.html
   - Test is_visual_fix returns False for .py/.js/.ts
   - Test compare_screenshots passes for identical images
   - Test compare_screenshots fails for significantly different images
   - Test visual_validator never raises even if playwright not installed
   - Test pipeline skips visual check for Python files (mock)
   - Test pipeline rejects fix on visual regression (mock)

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- Visual fix on frontend file → Playwright runs, diff checked
- Logic fix on .py/.js file → visual check skipped entirely
- docs/progress.md updated: Step C4 DONE — v2.1.6 COMPLETE
```
