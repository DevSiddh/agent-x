# Agent-X v2.1.6 | Steps C3–C4 + C3b (PENDING — after C2)
# Multi-Language Executor + Classifier + Visual Validation

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

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- All 4 new language categories classified correctly
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
