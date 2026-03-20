# Agent-Y | Build Roadmap
# Last updated: 2026-03-20
# Agent-Y v1 — reasoning layer for Agent-X

---

## v1 Done Condition
agent_y/reasoner.py passes all tests.
phase2/pipeline.py wired — 5/5 synthetic cases still accepted.
ReasonerError fallback path tested end-to-end.
"reasoner.ok" or "reasoner.fallback" appears in logs for every case.

---

## Build Philosophy (inherited)
- Spike first — prove JSON reasoning works on 3+ categories before building module
- One module at a time — tests pass before wiring into pipeline
- Reasoner is OPTIONAL — fallback path must work too
- Data gate before v1.1: 20+ real runs + autoresearch Check 4 passes

---

## STEP A0 — Spike (Validate JSON Reasoning)
Priority: PROVE IT WORKS

| Task | File |
|------|------|
| JSON reasoning spike | spike/run_spike_y.py |

Spike spec:
- Load syn_001, syn_003, syn_004 (3 categories: DependencyError, ConfigError, RuntimeError)
- Call DeepSeek with JSON-demand reasoning prompt
- strip_markdown_fences() → find first `{` → json.loads()
- Validate 5 required keys: action, reasoning, strategy, confidence, files_to_change
- Print PASS (all keys present, strategy non-empty) or FAIL (exact error)

Success = valid JSON with all 5 keys for 3/3 categories.
Failure = tells us if prompt needs stricter constraints or JSON schema must be simpler.

DO NOT skip this step. If spike fails → fix prompt before writing any module code.

---

## STEP A1 — Reasoner Module
Priority: CORE MODULE

| Task | File | Tests | Fixes |
|------|------|-------|-------|
| ReasonerOutput model | agent_y/reasoner.py | tests/test_reasoner.py | — |
| ReasonerError class | agent_y/reasoner.py | tests/test_reasoner.py | — |
| reason() function | agent_y/reasoner.py | tests/test_reasoner.py | P1 P2 P3 P4 |
| validate_strategy() | agent_y/reasoner.py | tests/test_reasoner.py | P1 |
| _filter_files() | agent_y/reasoner.py | tests/test_reasoner.py | P4 |
| _extract_json() | agent_y/reasoner.py | tests/test_reasoner.py | P2 |

Rules:
- ReasonerOutput: Pydantic v2 — action in {"repair","observe","escalate"}, len(files_to_change) ≤ 3
- reason(): strip fences → json.loads → validate schema → validate_strategy → _filter_files
- Max 2 retries — retry prompt includes parse/validation error + required keys list (not identical prompt)
- After 2 retries → raise ReasonerError
- confidence stored as-is — logged, never used in any conditional
- DEEPSEEK_API_KEY lazy inside function
- structlog on every call: category, strategy, confidence, attempt
- __main__ smoke test with mock DeepSeek response (no real API call)

---

## STEP A2 — Wire into Pipeline
Priority: INTEGRATION

| Task | File |
|------|------|
| Slot Reasoner between ContextBuilder and DeepSeekWorker | phase2/pipeline.py |
| try/except ReasonerError → enriched_context fallback | phase2/pipeline.py |
| Log reasoner.ok / reasoner.fallback per case | phase2/pipeline.py |
| Add 2 pipeline tests for Reasoner path | tests/test_pipeline.py |
| Pipeline re-run: 5/5 still accepted | — |

Pipeline change (minimal — two lines added):
  Before: context → generate_patch()
  After:  context → reason() (try/except) → enriched_context → generate_patch()

DONE WHEN:
- pytest tests/ → 206+ pass (zero regressions)
- python phase2/pipeline.py → 5/5 accepted
- Logs show reasoner.ok or reasoner.fallback for each case

---

## STEP A3 — Autoresearch Calibration Gate
Priority: DATA GATE (not code)

NOT a code step. A measurement step before v1.1.

Run pipeline 20+ times on real repos or synthetic cases.
For each run, record: strategy → patch outcome.
Evaluate autoresearch 4-check rubric:
  Check 1: Output parses cleanly (no fence stripping needed)?
  Check 2: strategy matches error category semantically?
  Check 3: files_to_change contains only relevant files?
  Check 4: Applying strategy → improved patch acceptance rate?

Gate: 3/3 checks pass for 10 consecutive runs.
YES → v1.1 (local model) unlocked.
NO  → refine reasoning prompt, repeat.

---

## Status Tracker

| Step | Description | Status |
|------|-------------|--------|
| Step A0 | Spike — JSON reasoning validated (3 categories) | PENDING |
| Step A1 | reasoner.py + ReasonerOutput + tests | PENDING |
| Step A2 | Wire into pipeline.py (5/5 still accepted) | PENDING |
| Step A3 | Autoresearch gate (20+ runs, Check 4) | PENDING |

---

## STEP A4 — Agent-Y v1.1: Prompt Loader + Local Model
Priority: TRIGGERED (not time-based)
Trigger condition: real prod repos with sensitive code, OR monthly bill > $30

| Task | File | Tests |
|------|------|-------|
| prompt_loader.py | agent_y/prompt_loader.py | tests/test_prompt_loader.py |
| Local model switch in reasoner.py | agent_y/reasoner.py | existing test_reasoner.py |

Key design:
- REASONER_MODEL env var: "deepseek-reasoner" (default) or "ollama/qwen2.5:7b"
- load_system_prompt() builds system prompt from CLAUDE.md + agent_y/CLAUDE.md + rules
- Ollama uses OpenAI-compatible endpoint: http://localhost:11434/v1
- DeepSeek path unchanged — no regression
- Switch = change one line in .env, nothing else

DONE WHEN: pipeline runs with REASONER_MODEL=ollama/qwen2.5:7b, reasoner.ok logged locally

---

## Upgrade Queue
v1.2 → multi-step reasoning chain (Plan → Verify → Patch)
v2.0 → Agent-Y as standalone orchestrator, Agent-X as tool-calling worker

---

## Key Decisions (locked)
1. Reasoner = reasoning only — NEVER generates code
2. Confidence = metadata only — never used for safety decisions
3. files_to_change = hard cap 3, filtered to context files only
4. ReasonerError = graceful degrade — pipeline must work without Reasoner
5. JSON extraction = strip_markdown_fences() + find first `{` (reuses existing sanitiser)
6. Strategy validation = keyword check against error category before returning
7. Local models = AFTER data gate — not before
