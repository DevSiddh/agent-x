# Agent-X | Enterprise Features Roadmap
# Created: 2026-03-22 — CH Y SAI SIDDHARDHA
# These are the ideas that separate a tool from a platform.
# Cost: $0 — all run on existing data, no new APIs, no GPU.
# Status: PENDING — implement after v3.0 foundation is stable

---

## WHY THESE MATTER

Most AI coding tools are black boxes. You run them, something happens, you hope it worked.
Agent-X is different — it has memory, it learns, it explains itself.
These three features make that visible, measurable, and self-improving.

No other tool in any language or stack has all three together.
Not Copilot. Not Devin. Not OpenClaw.

---

## FEATURE 1 — Live Intelligence Dashboard

### What it is
A real-time web UI showing Agent-X thinking and working.
Not logs. Not a terminal. A live view of every decision as it happens.

### What it shows
```
┌─────────────────────────────────────────────────────┐
│  Agent-X Live — 3 events today                      │
├─────────────────────────────────────────────────────┤
│  [LIVE] org/repo — DependencyError                  │
│  Confidence: 0.99 | Strategy: add setuptools        │
│  Thompson arm score: 0.94 (47 wins, 3 losses)       │
│  Patch: +1 line to requirements.txt                 │
│  Tests: 12 passed → ACCEPTED ✓                      │
├─────────────────────────────────────────────────────┤
│  Thompson Scores (live)                             │
│  DependencyError  ████████████ 0.94                 │
│  ConfigError      ████████░░░░ 0.81                 │
│  RuntimeError     ██████░░░░░░ 0.72                 │
│  EnvironmentError █████░░░░░░░ 0.65                 │
├─────────────────────────────────────────────────────┤
│  Memory: 340 entries | Accepted: 101 | Rate: 89%    │
│  Gateway hits today: 12 (zero LLM cost)             │
│  DeepSeek calls today: 8 | Cost: ~$0.04             │
└─────────────────────────────────────────────────────┘
```

### Why it's enterprise-level
- Makes AI decision-making transparent — nobody else does this
- One screen showing a live fix = better than any pitch deck
- Operators can watch the system learn in real time
- Investors/clients see ROI immediately (cost per fix, acceptance rate)

### Tech stack
```
Streamlit — free, pure Python, zero new infrastructure
Reads: memory.jsonl + thompson_state.json (already exist)
Polls every 5 seconds — no websocket needed
Cost: $0
Build time: 1-2 days
```

### Step: E0 (after v3.0)

---

## FEATURE 2 — Failure Intelligence Engine

### What it is
When a fix is rejected, the system doesn't just log "rejected" —
it classifies WHY it failed and feeds that back to improve future attempts.

### Current state
```
Fix rejected → decision="rejected" → Thompson update(0) → forgotten
```

### With Failure Intelligence
```
Fix rejected → rejection classifier runs → root cause identified
            → specific improvement triggered
            → next attempt uses different strategy
            → memory records: what failed + why + what worked instead
```

### Rejection root causes + automatic fixes
```
CAUSE                    DETECTION                 AUTO-FIX
─────────────────────────────────────────────────────────────
Wrong file targeted    → patch path ≠ error path  → improve context builder
Syntax error in patch  → git apply exit 1         → tighten sanitiser
Tests still fail       → same failures after      → retry with different strategy
Patch too large        → line count > 15           → prompt: "use simpler approach"
RAG mismatch           → similar fix, different   → lower TF-IDF score weight
                          outcome
Incomplete fix         → new failures added        → escalate to multi-file
```

### Why it's enterprise-level
- System learns from every failure, not just success
- Over time: rejection rate drops automatically without human intervention
- Compounds — 1000 failures = 1000 improvements to prompt strategy
- No other agentic system has explicit failure root cause analysis

### Tech stack
```
Pure Python — regex classification of rejection reasons
No LLM call needed
Adds: rejection_reason field to MemoryEntry
Cost: $0
Build time: 2-3 days
```

### Step: E1 (after E0)

---

## FEATURE 3 — Cross-Repo Pattern Engine (Self-Writing Gateway)

### What it is
The system analyzes memory.jsonl across ALL repos,
finds patterns that work everywhere,
and automatically writes new gateway rules — no human needed.

### Current state
```
Gateway rules: written manually by human (4 rules today)
New rule process: human notices pattern → human writes rule → human tests it
```

### With Cross-Repo Pattern Engine
```
Memory engine runs nightly analysis:
  "ModuleNotFoundError:setuptools appears in 47 repos — 98% acceptance rate"
  → auto-generates gateway rule
  → tests it against historical data
  → if precision > 95% → adds to GATEWAY_RULES automatically
  → logs: "new rule auto-added: setuptools_missing"

Human wakes up to: "3 new gateway rules generated overnight"
```

### The algorithm
```python
def find_new_gateway_candidates(memory: list[MemoryEntry]) -> list[Rule]:
    # 1. Group by bug_signature (strip repo prefix)
    # 2. Count cross-repo occurrences
    # 3. Filter: count >= 5 AND acceptance_rate >= 0.90
    # 4. Extract: common patch pattern across all accepted fixes
    # 5. Generate: regex pattern + fix function skeleton
    # 6. Validate: test against historical entries (precision > 0.95)
    # 7. Return: candidate rules for auto-addition
```

### Why it's enterprise-level
- Gateway rules grow automatically as data accumulates
- System improves itself without human intervention
- At 10,000 entries: hundreds of gateway rules covering every common pattern
- Zero marginal cost per new rule — pure data mining
- This is genuine machine learning from production data

### Tech stack
```
Pure Python — analytics on existing memory.jsonl
No LLM, no GPU, no new infrastructure
Runs as nightly cron job or on-demand
Cost: $0
Build time: 3-5 days
```

### Step: E2 (after E1)

---

## COMBINED IMPACT

When all three are running:

```
New CI failure arrives
        ↓
Cross-repo engine already has a rule for it → Gateway fixes in 0 seconds
        ↓ (if no rule)
Pipeline runs → Dashboard shows every decision live
        ↓ (if rejected)
Failure engine classifies why → improves next attempt automatically
        ↓ (if accepted)
Cross-repo engine notes the pattern → may auto-generate new gateway rule
        ↓
System is measurably smarter after every single run
```

No human writes rules. No human tunes prompts. No human monitors logs.
The system observes, classifies, improves, and explains itself.

That is what separates a script from a platform.

---

## BUILD ORDER

| Step | Feature | After | Time |
|------|---------|-------|------|
| E0 | Live Dashboard | v3.0 | 1-2 days |
| E1 | Failure Intelligence | E0 | 2-3 days |
| E2 | Cross-Repo Pattern Engine | E1 | 3-5 days |

Total: ~1 week. Cost: $0.

---

## DATA GATES

| Feature | Gate |
|---------|------|
| E0 Dashboard | Any data — build anytime |
| E1 Failure Intelligence | 50+ rejected runs to validate classifier |
| E2 Cross-Repo Engine | 500+ accepted runs across 5+ repos |
