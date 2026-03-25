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
- **Concrete solution: Two-layer deterministic verification — both in regression.py, $0 cost**

  Layer 1 — Negative Test Check (stops placebo patches):
  ```
  Step 1 — Verify failure:    run specific failing test on BROKEN code → must FAIL
                               if it passes → test is weak → escalate to human, reject patch
  Step 2 — Verify fix:        run specific failing test on PATCHED code → must PASS
  Step 3 — Verify regression: run full suite → no new failures
  ```

  Layer 2 — Shadow Type Check (stops type contract violations):
  ```bash
  python -m mypy --check-untyped-defs {patched_file} --no-error-summary
  ```
  Catches: `return True` when function is annotated `-> float`, wrong return types,
  broken interfaces. One subprocess call. Works in pipeline and extension context.
  Limitation: only applies to codebases with type annotations — partial coverage,
  still better than nothing. Skip silently if mypy not installed.

  Rejected approaches:
  - Property fuzzing (hypothesis/atheris) — heavy, narrow, only pure functions
  - Agent-Y self-review — subjective, expensive, v3.0 only if these two are insufficient
  - Docstring contract check — most real repos have no doctest examples

- **Build at:** D0 — both layers go into regression.py, no new dependencies beyond mypy
- **Status:** SOLUTION LOCKED — implement both layers at D0

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
  - Done: Bandit security scan (C1) — catches unsafe patterns
  - Done: Multi-run verification (C1) — rejects flaky fixes
  - Next: Negative Test Check (see R1) — deterministic, $0, implement at D0
  - Rejected: Property-based testing (Hypothesis) — we fix other people's repos, can't add their tests
  - Rejected: Docstring contract check (doctest) — most real repos have no doctest examples
  - Deferred: Agent-Y self-review — subjective, expensive, v3.0 only if Negative Test Check insufficient
- **Status:** SOLUTION LOCKED — Negative Test Check at D0 closes this

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

### L5a — Classifier pattern weights: strict vs noisy signals (locked 2026-03-22)
- **Rule:** Regex patterns fall into two classes — never mix their weights
  ```
  Strict signal  → exact exception class name (AssertionError, ModuleNotFoundError)
                 → weight 0.85–0.99 — can trigger pipeline alone
  Noisy signal   → human-readable phrases ("assert.*failed", "connection refused")
                 → weight 0.60–0.75 — corroborating only, cannot trigger alone
  ```
- **Why:** Enterprise CI logs contain "assertion failed" in passing test output,
  health checks, middleware logs. A 0.90 weight on a noisy pattern = false positives
  on real repos. A noisy pattern at 0.70 needs other evidence to cross the 0.85 gate.
- **Applied:** AssertionError=0.90 (strict), assert.*failed=0.70 (noisy)
- **Status:** RULE LOCKED — apply to every new pattern added to regex_pass.py

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

## v3.0 GAPS (Gemini audit — 2026-03-26)

---

### G1 — Dependency Deadlock (no INSTALL_DEPS action)
- **What happens:** Agent-Y plans "import redis" → Agent-X writes it → pytest fails ModuleNotFoundError → Agent-Y replans → Agent-X rewrites code to avoid redis → architecture ruined
- **Root cause:** TaskAction enum has no mechanism to install packages
- **Fix:** Enforce rule: Agent-Y must add a `requirements.txt` update task BEFORE any task that imports a new library. Orchestrator rejects any task importing an uninstalled package.
- **Status:** PENDING — fix before integration test

### G2 — state.json RAM Bomb
- **What happens:** 40-task project + full error tracebacks logged → state.json grows to 5MB+ → atomic write every loop iteration → CPU spikes + GC pauses on 2GB VPS
- **Fix:** Rolling window in StateManager — keep last 5 error entries, archive rest to `.agent/errors.log`
- **Status:** PENDING — fix in StateManager before v3.2

### G3 — Best-of-N Test Pollution
- **What happens:** Variant A writes corrupted SQLite row or rogue `/tmp/` file → rollback resets code but not environment → Variant B fails even if code is perfect
- **Fix:** Enforce `tmp_path` fixtures in all AcceptanceCriteria test cases. Add to AcceptanceCriteria spec in v30_creation_steps.md.
- **Status:** PENDING — add to spec before integration test

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
  OOM kill, server reboot, infinite retry loop — all fail silently, no alert, no log
- **Concrete solution: Inverted Monitoring Stack (3 layers, ~6 lines of code)**

  Layer 1 — NSSM (Windows OS daemon):
  Wraps runner.py as a Windows service. OS restarts it on crash or reboot.
  Equivalent to systemd on Linux. Free, 1 config file.
  `nssm install agent-x-runner python runner.py`

  Layer 2 — Healthchecks.io (Dead Man's Switch):
  runner.py pings a URL at end of every successful poll loop.
  If pings stop (OOM, crash, infinite loop) → healthchecks.io emails you.
  ```python
  if HEALTHCHECK_URL:
      requests.get(HEALTHCHECK_URL, timeout=5)
  ```

  Layer 3 — ntfy.sh (1-line push alert for fatal errors):
  GitHub token expired, DeepSeek down, queue locked → phone notification instantly.
  No auth required. Replace with Telegram bot at v3.2.
  ```python
  def alert(msg: str) -> None:
      if NTFY_TOPIC:
          requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg, timeout=5)
  ```

  Add to .env: HEALTHCHECK_URL, NTFY_TOPIC
  Add to .env.example: same keys, empty values

- **Gate:** Build when running 24/7 (not needed for dev sessions)
- **Status:** SOLUTION LOCKED — validated by Gemini

---

### I2b — Thompson update strategy per decision type (locked 2026-03-22)
- **Rule:** Different decisions carry different penalties — never treat all failures equally
  ```
  accepted    → update(reward=1)      → α+1  — strategy works, reinforce
  rejected    → update(reward=0)      → β+1  — bad patch, try different strategy
  abstained   → no update             → —    — no signal, don't learn from noise
  structural  → update(reward=0, penalty=5) → β+5  — hard wall, stop wasting tokens
  ```
- **Why β+5 on structural:**
  structural = architectural limit, not a bad guess. Treating it like rejected (β+1)
  wastes 3 retries on strategies that will all hit the same wall.
  β+5 means next time the same bug_signature appears → low Thompson score →
  system escalates instantly → zero API cost → human gets it immediately.
- **Build at:** Step AUDIT (penalty param) + Step D1 (GitHub issue on structural)
- **Status:** SOLUTION LOCKED

---

### I3 — Thompson cold start + arm explosion at enterprise scale
- **What happens:** New category/language seen → Beta(1,1) → random strategy
  Naive fix: multiply all dimensions → arm explosion → permanent cold start
- **Current mitigation:** Confidence gate (0.85) blocks low-confidence classifications
- **Gap:** Correct classification + wrong strategy = bad fix + memory poisoning

- **Concrete solution: Context-Factored Arms + Hierarchical Prior Seeding + Linear Fade**

  PART 1 — Arm naming convention (Category × Ecosystem):
  ```
  Arms = "{Category}_{Ecosystem}"
  e.g.  DependencyError_Python, DependencyError_Node, RuntimeError_Java
  ~30 arms total (10 categories × 3 ecosystems) — trivial convergence
  Exclude: repo size (handled by 15-line structural cap), framework, file size
  ```
  BREAKING CHANGE at C3b: migrate existing arms:
  ```
  "DependencyError" → "DependencyError_Python"
  "RuntimeError"    → "RuntimeError_Python"
  (all existing arms get _Python suffix — migration script required)
  ```

  PART 2 — Seeding new arms (two scenarios, different decay factors):
  ```python
  SIMILAR_CATEGORY = {
      "ImportError": "DependencyError", "ModuleNotFoundError": "DependencyError",
      "AttributeError": "RuntimeError",  "TypeError": "RuntimeError",
      "KeyError": "ConfigError",         "ValueError": "ConfigError",
  }
  BURN_IN = 10

  def seed_new_arm(arm_key, arms, global_stats):
      category, ecosystem = arm_key.split("_", 1)

      # Scenario A: new language for known category
      # e.g. DependencyError_Node, DependencyError_Python exists
      known_sibling = f"{category}_Python"
      if known_sibling in arms:
          a, b = arms[known_sibling]
          return (a * 0.25, b * 0.25)    # 25% — harder boundary than category similarity

      # Scenario B: new category — use similar category in same ecosystem
      similar_cat = SIMILAR_CATEGORY.get(category)
      if similar_cat:
          sibling = f"{similar_cat}_{ecosystem}"
          if sibling in arms:
              a, b = arms[sibling]
              return (a * 0.50, b * 0.50)  # 50% — same ecosystem, related category

      # Scenario C: global category average × 0.25
      if global_stats:
          return (global_stats.avg_success * 0.25 * 2,
                  global_stats.avg_failure * 0.25 * 2)
      return (2.0, 1.0)

  def blended_sample(arm, seed, n_attempts):
      if n_attempts >= BURN_IN:
          return arm
      weight = 1 - (n_attempts / BURN_IN)
      return (arm.alpha + seed.alpha * weight, arm.beta + seed.beta * weight)
  ```

- **Build at:** C3b (when multi-language lands — arm migration happens here)
- **Status:** SOLUTION LOCKED — validated Claude + Gemini independently

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

### S0 — memory.jsonl concurrent write corruption
- **What happens:** Multiple workers append to memory.jsonl simultaneously
  → interleaved bytes → invalid JSON lines → memory store broken silently
- **Current state:** Single poll loop = safe right now. Breaks when parallel workers added.
- **Solution:** SQLite memory_buffer table → single-threaded flush every 60s
  Workers INSERT into SQLite (handles locking automatically)
  runner.py flushes buffer → appends to memory.jsonl → deletes flushed rows
- **Gate:** Build when adding multiple concurrent workers (not urgent now)
- **Status:** SOLUTION LOCKED — see architecture_decisions.md D13

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
