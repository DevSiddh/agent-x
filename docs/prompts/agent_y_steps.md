# Agent-Y v1 | Steps A0–A2 (DONE — archived)
# All steps here are COMPLETE. Load only for reference.

---

## STEP A0 — Agent-Y Spike (Validate JSON Reasoning)
# First Agent-Y step. Spike before building any module.

```
You are validating Agent-Y v1 — reasoning layer for Agent-X.
Read CLAUDE.md, docs/progress.md, agent_y/CLAUDE.md before touching anything.
All Agent-X steps (0–14) must be DONE. 206 tests must pass. Check first.

BUILD THIS STEP:

Create spike/run_spike_y.py — throwaway validation, ~60 lines:
- Load syn_001, syn_003, syn_004 from phase1/dataset/synthetic.jsonl
  (3 categories: DependencyError, ConfigError, RuntimeError)
- For each case:
  - Build context string: error_lines + category + affected_file
  - Call DeepSeek (base_url=https://api.deepseek.com, model=deepseek-chat)
  - System prompt:
    "You are a reasoning engine. Return ONLY valid JSON. No markdown. No fences.
     Required keys: action, reasoning, strategy, confidence, files_to_change.
     action must be one of: repair, observe, escalate.
     confidence is float 0.0-1.0.
     files_to_change is a list of strings (max 3 files)."
  - User prompt: context string + "What is the best fix strategy for this error?"
  - strip_markdown_fences() → find first '{' → json.loads()
  - Validate all 5 required keys present
  - Print PASS (all keys present, strategy non-empty) or FAIL (exact reason)

DONE WHEN:
- Script runs without crash
- 3/3 categories return parseable JSON with all 5 required keys
- strategy field is non-empty and error-specific for each case
- docs/progress.md updated: Step A0 DONE

If any case FAILS: report exact failure point. Do not proceed to Step A1.
```

---

## STEP A1 — Agent-Y Reasoner Module

```
You are building Agent-Y v1 — reasoning layer for Agent-X.
Read CLAUDE.md, docs/progress.md, agent_y/CLAUDE.md, docs/agent_y_problems.md before touching anything.
Step A0 spike must PASS before building this.

BUILD THIS STEP:

1. agent_y/__init__.py — empty package init

2. agent_y/reasoner.py
   Classes:
   - ReasonerOutput: Pydantic v2
     Fields: action: str, reasoning: str, strategy: str,
             confidence: float, files_to_change: list[str]
     Validators: action in {"repair","observe","escalate"}, len(files_to_change) <= 3
   - ReasonerError(Exception): raised after max retries exhausted

   Functions:
   - reason(context: str, classification: ClassifierResult) -> ReasonerOutput
     Flow:
       1. Build reasoning prompt (context + category + required JSON schema)
       2. Call DeepSeek — DEEPSEEK_API_KEY lazy (inside function, not module level)
       3. _extract_json() → json.loads()
       4. Validate all 5 keys present (KeyError → retry)
       5. validate_strategy(strategy, category) → if False → retry (P1)
       6. _filter_files(files_to_change, context, affected_file) → cap at 3 (P4)
       7. Return ReasonerOutput
       Retry: max 2 — retry prompt MUST include error message + required keys list
       After 2 retries: raise ReasonerError
   - validate_strategy(strategy: str, category: str) -> bool
     CATEGORY_KEYWORDS dict maps category → keyword list
     Return True if any keyword found in strategy.lower()
   - _filter_files(files: list[str], context: str, affected_file: str) -> list[str]
     Keep only files mentioned in context or matching affected_file, cap at 3
   - _extract_json(raw: str) -> dict
     strip_markdown_fences() → find first '{' → json.loads()
   - structlog on every call: category, strategy, confidence, attempt
   - confidence: stored as-is — logged only, NEVER used in any decision
   - __main__ smoke test with mock DeepSeek response (no real API call)

3. tests/test_reasoner.py
   - Test ReasonerOutput validates action in allowed set
   - Test ReasonerOutput rejects more than 3 files_to_change
   - Test reason() returns ReasonerOutput on valid mock response
   - Test reason() retries on JSON parse failure (mock bad JSON first attempt)
   - Test reason() raises ReasonerError after 2 failed retries
   - Test validate_strategy returns True for matching pairs (DependencyError + "install dependency")
   - Test validate_strategy returns False for mismatched pairs (DependencyError + "rename variable")
   - Test _filter_files caps at 3 and removes unrelated files
   - Test _extract_json handles fenced JSON (```json wrapper)
   - Test confidence never appears in any branching logic

DONE WHEN:
- pytest tests/test_reasoner.py → all pass
- python agent_y/reasoner.py → smoke test prints ReasonerOutput
- docs/progress.md updated: Step A1 DONE
```

---

## STEP A2 — Wire Reasoner into Pipeline

```
You are wiring Agent-Y into Agent-X's pipeline.
Read CLAUDE.md, docs/progress.md, agent_y/CLAUDE.md before touching anything.
Step A1 must be DONE — tests/test_reasoner.py all passing.
206+ Agent-X tests must still pass after this step. Do not break them.

CHANGE phase2/pipeline.py:

Before (current):
  context = build_context(classifier_result, fixture_path)
  worker_result = generate_patch(cleaned, classifier_result, context)

After (new):
  context = build_context(classifier_result, fixture_path)
  # Agent-Y reasoning (optional — fallback to raw context on error)
  try:
      from agent_y.reasoner import reason, ReasonerError
      reasoner_output = reason(context, classifier_result)
      log.info("reasoner.ok", strategy=reasoner_output.strategy,
               confidence=reasoner_output.confidence)
      enriched_context = context + "\n\nSTRATEGY: " + reasoner_output.strategy
  except ReasonerError as e:
      log.warning("reasoner.fallback", error=str(e))
      enriched_context = context  # baseline — Agent-X continues without reasoning
  worker_result = generate_patch(cleaned, classifier_result, enriched_context)

Rules:
- Import reason lazily inside run() — not at module top
- ReasonerError caught here — never propagates to outer pipeline (P5)
- enriched_context = context + strategy hint only — no schema leakage
- reasoner_output.confidence logged but NOT passed to any gate (P3)

UPDATE tests/test_pipeline.py:
- Add test: reason() called between build_context and generate_patch (mock)
- Add test: ReasonerError caught → pipeline continues with raw context (mock raises ReasonerError)
- All 7 existing pipeline tests must still pass unchanged

FINAL RUN (no mocks):
python phase2/pipeline.py
→ 5/5 cases accepted
→ logs show "reasoner.ok" or "reasoner.fallback" for every case

DONE WHEN:
- pytest tests/ → all 206+ pass (zero regressions)
- python phase2/pipeline.py → 5/5 accepted
- "reasoner.ok" or "reasoner.fallback" in logs for every case
- docs/progress.md updated: Step A2 DONE — Agent-Y v1 COMPLETE
```
