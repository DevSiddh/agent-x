# Agent-Y | Context
# Max 80 lines — index only
# Last updated: 2026-03-20

---

## What Is Agent-Y
Reasoning layer for Agent-X. Slots between ContextBuilder and DeepSeekWorker.
Decides HOW to fix before DeepSeekWorker generates the patch.

---

## Role in Pipeline
Observer → LogParser → Classifier → SafetyGate → ThompsonSampler.sample()
→ ContextBuilder → [Agent-Y Reasoner] → DeepSeekWorker → Sanitiser
→ Executor → RegressionCheck → DecisionEngine → ThompsonSampler.update() → MemoryStore

---

## ReasonerOutput Schema (Pydantic v2)
action:          "repair" | "observe" | "escalate"
reasoning:       str   — why this strategy was selected
strategy:        str   — concrete approach description
confidence:      float — 0.0–1.0, metadata only, NOT used in decisions
files_to_change: list[str] — ≤ 3 files, only files in error context

---

## Hard Constraints
- Reasoner: reasoning + strategy ONLY — never generates code or patches
- files_to_change: ≤ 3 items, only files referenced in error context
- ReasonerError → pipeline falls back to baseline (direct patch gen), NEVER blocks
- confidence: logged as metadata only, never used in safety gate or decisions
- strategy MUST relate to classified error category (validated before return)
- JSON schema validated after json.loads — not just parse success

---

## Error Category → Strategy Validation
DependencyError  → strategy must reference: dependency / package / install / requirements
EnvironmentError → strategy must reference: env / build / config / variable
ConfigError      → strategy must reference: import / config / missing / module
RuntimeError     → strategy must reference: schema / type / model / namespace
NetworkError     → strategy must reference: connection / retry / timeout / network

---

## Retry Rules
Max retries: 2
On retry: prompt includes json.JSONDecodeError message + required keys list
After 2 retries: raise ReasonerError → pipeline continues with raw context

---

## v1 Scope
Phase 1: agent_y/reasoner.py — single module
         Spike first (spike/run_spike_y.py) on 3+ error categories
         Wire into phase2/pipeline.py with minimal changes

---

## Data Sources (v1 — read-only)
Shared: memory/memory.jsonl — read via get_similar() from phase2.memory.store
No new storage in v1

---

## Autoresearch Gate (before v1.1)
Check 1: Output parses cleanly without stripping fences?
Check 2: strategy matches error category semantically?
Check 3: files_to_change contains only relevant files?
Check 4: Does applying strategy lead to improved patch acceptance rate?
Gate: 3/3 checks pass for 10 consecutive runs → v1.1 (local model) unlocked

---

## Key Files
→ @agent_y/reasoner.py          — Reasoner implementation
→ @docs/agent_y_problems.md     — P1..P5 risks
→ @docs/agent_y_roadmap.md      — build steps A0..A3
→ @docs/progress.md             — Agent-Y status section
→ @docs/session_prompts.md      — steps A0..A2
