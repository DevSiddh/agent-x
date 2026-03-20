# Agent-Y | Problems & Solutions
# Last updated: 2026-03-20
# Mirrors problems_and_solutions.md format — Agent-Y specific risks only

---

## P1 — Valid JSON, wrong strategy (silent failure)

- **Phase:** v1 / Reasoner
- **File:** agent_y/reasoner.py
- **Problem:** DeepSeek returns valid JSON that parses cleanly but strategy is semantically
  wrong. Example: error=MissingDependency, strategy="rename variable".
  json.loads succeeds → system continues silently with useless reasoning.
- **Solution:** Validate strategy against classified error category before returning:
  ```python
  CATEGORY_KEYWORDS: dict[str, list[str]] = {
      "DependencyError":  ["dependency", "package", "install", "requirements"],
      "EnvironmentError": ["env", "build", "config", "environment", "variable"],
      "ConfigError":      ["import", "config", "missing", "module"],
      "RuntimeError":     ["schema", "type", "model", "namespace", "conflict"],
      "NetworkError":     ["connection", "retry", "timeout", "network"],
  }

  def validate_strategy(strategy: str, category: str) -> bool:
      keywords = CATEGORY_KEYWORDS.get(category, [])
      return any(kw in strategy.lower() for kw in keywords)
  ```
  If validation fails → treat as parse failure → retry → after 2 retries → ReasonerError.
- **Status:** PENDING — implement in agent_y/reasoner.py

---

## P2 — JSON wrapped in markdown fences

- **Phase:** v1 / Reasoner
- **File:** agent_y/reasoner.py
- **Problem:** DeepSeek wraps JSON output in ```json fences even when explicitly told not to.
  json.loads fails on raw response. Same pattern as P3 in phase2.
- **Solution:** Re-use strip_markdown_fences() from phase2.patch_gen.sanitiser,
  then find first `{` and parse from there:
  ```python
  from phase2.patch_gen.sanitiser import strip_markdown_fences

  def _extract_json(raw: str) -> dict:
      cleaned = strip_markdown_fences(raw)
      start = cleaned.find("{")
      if start == -1:
          raise json.JSONDecodeError("no JSON object found", cleaned, 0)
      return json.loads(cleaned[start:])
  ```
- **Status:** PENDING — implement in agent_y/reasoner.py

---

## P3 — LLM-reported confidence is unreliable

- **Phase:** v1 / Reasoner + Pipeline
- **File:** agent_y/reasoner.py, phase2/pipeline.py
- **Problem:** DeepSeek returns confidence=0.9 even for wrong strategies.
  If confidence is used in decisions → false safety.
  Existing safety gate uses our own regex confidence, not LLM confidence.
- **Solution:** Treat confidence as metadata only. Log it, never gate on it:
  ```python
  log.info("reasoner.output", confidence=output.confidence, strategy=output.strategy)
  # NEVER: if output.confidence > threshold: proceed
  ```
  Store in ReasonerOutput for future calibration only.
- **Status:** PENDING — enforce pattern in pipeline.py wiring (Step A2)

---

## P4 — Unrelated files in files_to_change (hallucination)

- **Phase:** v1 / Reasoner
- **File:** agent_y/reasoner.py
- **Problem:** LLM hallucinates files outside the error context. Wide changes
  break unrelated code and bypass the ≤ 15-line patch constraint downstream.
- **Solution:** Filter files to only those mentioned in context or matching affected_file.
  Hard cap at 3:
  ```python
  def _filter_files(
      files: list[str], context: str, affected_file: str
  ) -> list[str]:
      allowed = [f for f in files if f in context or f == affected_file]
      return allowed[:3]  # hard cap — always
  ```
- **Status:** PENDING — implement in agent_y/reasoner.py

---

## P5 — ReasonerError blocking pipeline (regression risk)

- **Phase:** v1 / Pipeline
- **File:** phase2/pipeline.py
- **Problem:** If Reasoner raises and pipeline doesn't catch it, the whole run crashes.
  Agent-X ran 5/5 without Agent-Y — that baseline must remain reachable.
- **Solution:** Wrap Reasoner call in try/except in pipeline.py. Fallback to raw context:
  ```python
  try:
      reasoner_output = reason(context, classifier_result)
      log.info("reasoner.ok", strategy=reasoner_output.strategy)
      enriched_context = context + "\n\nSTRATEGY: " + reasoner_output.strategy
  except ReasonerError as e:
      log.warning("reasoner.fallback", error=str(e))
      enriched_context = context  # Agent-X baseline — no reasoning
  ```
  Test this path explicitly in tests/test_pipeline.py (mock raises ReasonerError).
- **Status:** PENDING — implement in Step A2 (pipeline wiring)
