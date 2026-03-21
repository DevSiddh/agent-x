# Agent-X v2.1.5 | Steps C0–C2 (PENDING — after B3)
# Memory Engine + Pipeline Hardening + Gateway Stage

---

## STEP C0 — v2.1.5: Memory Engine (TF-IDF + Hybrid Ranking + Reuse Bypass)
# Prerequisite: Step B3 DONE. v2.1 complete. 20+ accepted entries in memory.jsonl.

```
You are building Agent-X v2.1.5 — Memory Engine upgrade.
Read CLAUDE.md, docs/progress.md before touching anything.
Step B3 must be DONE. Do not break existing tests.

CONTEXT:
Current get_similar() matches by category only — no real similarity scoring.
RAG is passive (enriches context only). Goal: make it an active decision maker.

BUILD THIS STEP:

1. Add test_summary field to MemoryEntry in phase2/memory/store.py
   - New field: test_summary: str = ""  (e.g. "12 passed, 0 failed")
   - Update pipeline.py to populate test_summary from regression.run_tests() result
   - Backward compatible — empty string default for old entries

2. phase2/memory/similarity.py — NEW FILE
   - MemoryEngine class
   - _load_successful(self) -> list[dict]
     Load only entries where decision="accepted" from memory/memory.jsonl
   - find_similar(self, bug_signature: str, affected_file: str) -> dict | None
     TF-IDF vectorizer on (error_type + bug_signature) strings
     cosine_similarity between new query and all past signatures
     Apply filename boost: score += 0.05 if affected_file matches file_context
     Hybrid ranking: final_score = 0.7 * similarity + 0.3 * (alpha / (alpha + beta))
       → get alpha/beta from thompson_state.json for each bug_signature arm
       → fallback to 0.5 if arm not found
     top-k = 3, threshold = 0.85
     Return best match dict with: patch, match_score, metadata — or None
   - structlog on every call, type hints, __main__ smoke test
   - library: sklearn (TfidfVectorizer, cosine_similarity) — add to requirements.txt

3. Update phase2/pipeline.py — Memory Reuse Bypass
   After RegexClassifier + PreSafetyGate, BEFORE ContextBuilder:
   ```
   engine = MemoryEngine()
   cached = engine.find_similar(classifier_result.bug_signature, classifier_result.affected_file)
   if cached:
       log.info("memory.reuse", score=cached["match_score"])
       apply cached["patch"] directly via runner.apply_patch()
       run regression check
       if accepted: write memory entry, return — SKIP Agent-Y and Agent-X entirely
       else: log.warning("memory.reuse.failed") — fall through to full pipeline
   ```

4. tests/test_similarity.py
   - Test find_similar returns None when memory empty
   - Test find_similar returns match above threshold for identical signature
   - Test find_similar returns None when best score below 0.85
   - Test filename boost increases score when file matches
   - Test hybrid ranking picks high-success-rate match over high-similarity match
   - Test reuse bypass in pipeline: mock find_similar returns match → Agent-Y not called
   - Test reuse bypass fallback: apply fails → pipeline continues normally

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- python phase2/pipeline.py → memory.reuse logged for repeated bugs
- docs/progress.md updated: Step C0 DONE — v2.1.5
```

---

## STEP C1 — v2.1.5: Pipeline Hardening (Multi-Run + Bandit + Structural Escalation)
# Prerequisite: Step C0 DONE.

```
You are hardening Agent-X v2.1.5 — pipeline integrity upgrades.
Read CLAUDE.md, docs/progress.md before touching anything.
Step C0 must be DONE. Do not break existing tests.

BUILD THIS STEP:

1. Multi-Run Verification in phase2/executor/regression.py
   - Add run_tests_stable(fixture_path: Path, runs: int = 3) -> TestReport
     Runs pytest runs times consecutively
     If ANY run fails → return TestReport with passed=False, note="flaky"
     Only returns passed=True if ALL runs pass
   - Update pipeline.py: use run_tests_stable() instead of run_tests() for final verification
   - Flaky result → decision="abstained", log.warning("executor.flaky") → never logged to memory
   - __main__ smoke test

2. Bandit Security Gateway in phase2/pipeline.py PostSafetyValidation step
   - After sanitiser.validate_patch() passes, before executor.apply_patch():
     Write patched file to temp location
     Run: subprocess.run(["bandit", "-q", "-r", target_file], capture_output=True)
     If returncode != 0 → reject patch, log.warning("security.bandit_fail", issues=stderr)
     Add bandit to requirements.txt
   - Never raises — wrap in try/except, log warning and continue if bandit not installed

3. Radon Complexity Check in phase2/pipeline.py PostSafetyValidation
   - After Bandit passes, run: subprocess.run(["radon", "cc", target_file, "-s"])
   - Parse output — if any function complexity score increases significantly vs before patch
     → log.warning("doctor.architecture_risk", complexity=score)
     → decision = "structural" (same as line limit escalation)
   - Add radon to requirements.txt
   - Never raises — wrap in try/except, log warning and continue if radon not installed

4. Structural Escalation label in phase2/pipeline.py DecisionEngine
   - Add decision="structural" to DecisionEngine
   - Trigger when: sanitiser rejected AND attempt == MAX_RETRIES (3)
     Meaning: system hit line limit 3 times → problem is architectural, not patchable
   - Log: log.warning("decision.structural", reason="exceeded line limit on all retries")
   - Write to memory with decision="structural" (never reused by MemoryEngine — filtered out)

5. tests/test_hardening.py
   - Test run_tests_stable: all pass → passed=True
   - Test run_tests_stable: one fail in 3 runs → passed=False, note="flaky"
   - Test bandit gate: rejects patch with hardcoded secret (mock bandit returncode=1)
   - Test bandit gate: passes clean patch (mock bandit returncode=0)
   - Test bandit gate: continues gracefully if bandit not installed
   - Test structural escalation: decision="structural" after 3 line-limit rejections

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- Flaky fixes never reach memory.jsonl
- Bandit rejects unsafe patches
- Structural bugs get labelled correctly
- docs/progress.md updated: Step C1 DONE — v2.1.5
```

---

## STEP C2 — v2.1.5: Gateway Stage (Regex Direct Fixes)
# Prerequisite: Step C1 DONE. Needs real run data to identify common patterns.
# Data gate: check memory.jsonl — identify top 3 most repeated bug_signatures first.

```
You are building Agent-X v2.1.5 — Gateway stage (zero-cost tier).
Read CLAUDE.md, docs/progress.md before touching anything.
Step C1 must be DONE.

PREREQUISITE CHECK:
Run: python -c "import json; from collections import Counter; sigs = [json.loads(l)['bug_signature'] for l in open('memory/memory.jsonl') if json.loads(l).get('decision')=='accepted']; print(Counter(sigs).most_common(5))"
If no pattern appears >= 3 times → STOP. Not enough data yet. Wait for more real runs.

BUILD THIS STEP:

1. phase2/gateway.py — NEW FILE
   - GATEWAY_RULES: list of rule dicts — pattern → direct fix function
     Each rule: {"pattern": regex, "category": str, "fix": Callable}
     Start with only patterns that appear >= 3 times in real memory.jsonl data
     Do NOT invent patterns — derive from actual data only
   - check(error_lines: list[str], fixture_path: Path) -> GatewayResult | None
     GatewayResult: Pydantic v2 — matched_rule, patch_applied, success
     Try each rule against error_lines
     If match: apply direct fix, run tests — if pass return GatewayResult
     If no match or fix fails: return None (fall through to full pipeline)
   - structlog on every match + result, type hints, __main__ smoke test

2. Update phase2/pipeline.py — add Gateway before ContextBuilder
   After PreSafetyGate, before ContextBuilder:
   ```
   gateway_result = gateway.check(cleaned, fixture_path)
   if gateway_result and gateway_result.success:
       log.info("gateway.hit", rule=gateway_result.matched_rule)
       write memory entry, return — SKIP everything after
   ```

3. tests/test_gateway.py
   - Test gateway returns None when no rule matches
   - Test gateway applies correct fix for matched pattern
   - Test gateway returns None if fix applied but tests fail
   - Test pipeline uses gateway before ContextBuilder (mock)

DONE WHEN:
- pytest tests/ → all pass
- At least 1 rule defined from real data
- gateway.hit logged for matching cases
- docs/progress.md updated: Step C2 DONE — v2.1.5 COMPLETE
```
