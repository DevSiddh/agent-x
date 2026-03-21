# Agent-X | Risks, Flaws & Danger Points
# Created: 2026-03-22
# Owner: CH Y SAI SIDDHARDHA
# Purpose: Honest audit of system weaknesses — find solutions before they become incidents
# Rule: Never close an item without a concrete solution + data gate

---

## CRITICAL RISKS (can cause real damage)

---

### R1 — Patch poisons memory (the silent killer)
- **What happens:** DeepSeek generates a patch → tests pass → stored as "accepted" in memory
  → RAG surfaces it for future similar bugs → system repeats a subtly wrong fix across repos
- **Why dangerous:** No semantic correctness check. Only test pass/fail. Tests can be incomplete.
- **Current mitigation:** Multi-run verification (3x) in regression.py — flaky fixes rejected
- **Gap:** Structural correctness not checked — patch can pass tests but degrade code quality
- **Solution path:** Agent-Y self-review at v3.0 — reasons about patch before accepting
  Intermediate fix: add `radon` complexity check (already in C1) — reject patches that
  increase cyclomatic complexity beyond threshold
- **Status:** PARTIALLY MITIGATED — full fix at v3.0

---

### R2 — Auto-PR ships unreviewed code (D1 risk)
- **What happens:** Patch passes tests → PR opened automatically → human approves without reading
- **Why dangerous:** Bad patch reaches main branch. If tests have gaps, bugs go to prod.
- **Current mitigation:** None yet — D1 not built
- **Solution path:**
  1. PR description always includes: diff, test results, confidence score, run_id
  2. PR title always includes [agent-x] prefix — easy to filter
  3. Branch protection: require human approval before merge (never auto-merge)
  4. Add PR checklist: "Did you read the diff?" in PR template
- **Status:** PENDING — design before building D1

---

### R3 — DeepSeek single point of failure
- **What happens:** DeepSeek API outage → entire pipeline stops → zero fixes possible
- **Why dangerous:** No fallback. All real-world runs depend on one API.
- **Current mitigation:** None
- **Solution path:**
  - Primary: DeepSeek-chat (current)
  - Fallback 1: GPT-4o-mini (cheap, reliable)
  - Fallback 2: Local Ollama model (offline, zero cost) — already in roadmap at A4
  - Implementation: try/except around API call → try next provider in chain
- **Gate:** Trigger when monthly DeepSeek bill >$30 OR when 2+ outages in one month
- **Status:** PENDING — low priority until outages occur

---

### R4 — Memory grows forever (performance cliff)
- **What happens:** memory.jsonl keeps growing → TF-IDF gets slow → similarity search degrades
- **When:** Estimated ~10,000+ entries before noticeable slowdown
- **Current state:** 340+ entries — fine for now
- **Solution path:**
  - Keep only accepted fixes in RAG index (rejected/abstained still logged but not indexed)
  - Prune duplicates: same bug_signature + same patch → keep latest only
  - Archive entries older than 90 days to memory_archive.jsonl
  - Switch to FAISS vector index when entries exceed 5,000
- **Gate:** Build pruning when memory.jsonl exceeds 1,000 entries
- **Status:** MONITORED

---

## LIMITATIONS (can't fix yet — need data or architecture)

---

### L1 — Single file only (multi-file bugs always escalate)
- **What happens:** Bug spans 2+ files → escalated → never fixed → accumulates in memory
- **Examples:** Missing import in A + broken interface in B, schema mismatch across files
- **Solution:** v3.0 Orchestrator — Agent-Y plans task sequence, one file per task
- **Gate:** v3.0 architecture (after D0, D1)
- **Status:** LOCKED

---

### L2 — No semantic correctness check (tests ≠ correct code)
- **What happens:** Patch makes tests green but code is subtly wrong
  e.g. hardcodes a value instead of fixing the root cause
- **Examples:** `return True` instead of fixing the actual logic
- **Solution path:**
  - Short term: Bandit security scan (already in C1) catches unsafe patterns
  - Medium term: Agent-Y reviews diff before accepting ("does this make sense?")
  - Long term: Property-based testing + mutation testing
- **Status:** PARTIALLY MITIGATED (Bandit) — full fix at v3.0

---

### L3 — BuildError always abstains (Docker logs have no tracebacks)
- **What happens:** Docker build fails → log has command that failed, not Python traceback
  → classifier finds no pattern → confidence 0.0 → observer mode
- **Solution:** Classify from Docker command that failed, not traceback
  ```
  "RUN pip install -r requirements.txt" + exit 1 → DependencyError
  "RUN python setup.py build" + exit 1 → BuildError:setup_failure
  ```
- **Gate:** 5+ real BuildError runs to map actual log patterns
- **Current:** 3x BuildError in memory — not enough
- **Status:** DATA-GATED

---

### L4 — No project architecture understanding
- **What happens:** Agent-Y plans a fix without knowing file layout
  → wrong file paths, missed imports, incorrect module references
- **Solution:** File tree reader (Step D0, item 1) — passes directory structure to Agent-Y
- **Status:** PLANNED — Step D0

---

### L5 — Confidence threshold is one number for all categories
- **What happens:** 0.85 works for DependencyError/ConfigError but may be wrong for
  RuntimeError (more complex, needs higher threshold) or new categories
- **Solution:** Per-category thresholds after calibration
  ```python
  THRESHOLDS = {
      "DependencyError": 0.80,   # high signal patterns
      "RuntimeError": 0.90,      # more ambiguous
      "unknown": 1.00,           # never act on unknown
  }
  ```
- **Gate:** 50+ runs per category before setting category threshold
- **Status:** PENDING — not enough per-category data yet

---

### L6 — No awareness of post-merge outcomes
- **What happens:** PR merged → patch deployed → prod breaks → Agent-X never knows
  → memory still records it as "accepted" → future runs repeat the bad fix
- **Solution:** GitHub webhook on PR merge + CI run on main branch
  → if post-merge CI fails → mark memory entry as "reverted" → Thompson update(0)
- **Gate:** Requires auto-PR (D1) to be built first
- **Status:** PENDING — after D1

---

## INFRASTRUCTURE FLAWS

---

### I1 — ngrok tunnel breaks on restart (webhook stops receiving)
- **What happens:** ngrok restarts → URL changes → GitHub webhook 404s → no real data
- **Impact:** All real-world data collection stops silently
- **Solution:** Static ngrok domain (free tier, one-time setup)
  ```bash
  ngrok http --domain=<your-static-domain>.ngrok-free.app 8000
  ```
- **Status:** PENDING — 5 minute fix, do before next webhook session

---

### I2 — No monitoring (pipeline failures are silent)
- **What happens:** webhook_worker.py crashes silently → queue fills up → nothing processed
- **Solution:** Heartbeat log every 60s + alert if no runs processed in 30 mins
  Simple: write last_run_at to a file → check it on startup
- **Status:** PENDING — low priority until running 24/7

---

### I3 — Thompson cold start on new error categories
- **What happens:** New category seen for first time → Beta(1,1) → random strategy
  → first 5-10 runs are essentially guesses
- **Current mitigation:** Confidence gate (0.85) blocks low-confidence classifications
- **Gap:** Correct classification + wrong strategy = bad fix + memory poisoning
- **Solution:** Seed new categories with prior from similar categories
  e.g. new "ImportError" category seeds from "DependencyError" prior
- **Status:** PENDING — build when 3+ new categories emerge

---

## SCALING CLIFFS (what breaks when files get huge)

---

### S1 — memory.jsonl TF-IDF gets slow
- **When:** ~10,000 entries (currently 340)
- **Symptom:** similarity search takes seconds → pipeline unusable
- **Fix:** Switch to FAISS vector index
  ```python
  # faiss.IndexFlatL2 — searches 1M entries in milliseconds
  # drop-in replacement for current TF-IDF in similarity.py
  ```
- **Gate:** Build when memory.jsonl exceeds 10,000 entries

---

### S2 — Context window hits ceiling
- **When:** 7+ RAG hits with full content + file tree + error log → 8,000+ tokens
- **Current:** 5 RAG hits ~500 tokens — fine
- **Fix:** Ranked verbosity (Gemini validated)
  ```
  Match #1 → full file content + diff
  Match #2-7 → diff + bug_signature only
  ```
- **Gate:** Build when RAG limit raised above 7 (after 200+ accepted runs)

---

### S3 — Git history bloats from memory.jsonl commits
- **When:** ~5,000+ commits with memory.jsonl growing each time
- **Symptom:** git clone becomes slow, repo size balloons
- **Fix:** Stop committing memory.jsonl to git
  Move to SQLite (same pattern as phase1/webhook/queue.db)
  Git tracks code only — never runtime data
- **Gate:** Build when memory.jsonl exceeds 5MB or 5,000 entries

---

### Timeline (nothing urgent yet)

| Problem | Starts at | Currently | Time to hit |
|---------|-----------|-----------|-------------|
| TF-IDF slow | 10,000 entries | 340 | months |
| Context ceiling | 15 RAG hits | 5 | far future |
| Git bloat | 5,000 commits | ~30 | far future |

---

## SOLUTION PRIORITY

| Risk | Priority | When to fix |
|------|----------|-------------|
| R2 — Auto-PR ships bad code | HIGH | Design before D1 |
| I1 — ngrok breaks | HIGH | Before next session |
| R1 — Memory poisoning | MEDIUM | v3.0 Agent-Y self-review |
| L2 — No semantic check | MEDIUM | v3.0 |
| R3 — DeepSeek SPOF | LOW | When bill >$30 or 2+ outages |
| L3 — BuildError | LOW | After 5+ real BuildError runs |
| L5 — Per-category thresholds | LOW | After 50+ runs per category |
| L6 — Post-merge awareness | LOW | After D1 |
| R4 — Memory growth | LOW | After 1,000+ entries |
| I2 — No monitoring | LOW | When running 24/7 |
| I3 — Thompson cold start | LOW | When 3+ new categories emerge |
| L1 — Single file limit | LOCKED | v3.0 Orchestrator |
| L4 — No architecture view | PLANNED | Step D0 |
