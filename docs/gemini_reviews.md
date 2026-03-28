# Gemini Reviews + Claude Evaluation Log
# Purpose: Gemini proposes → Claude evaluates → accepted/rejected with reason
# Format: same as chatgpt_reviews.md
# Last updated: 2026-03-28

---

## REVIEW 1 — Flywheel Evaluation Framework (2026-03-27)

**Topic:** How to prove Agent-XYZ is learning, not just caching

### Input (Gemini)
- ZSPR (Zero-Shot Pass Rate): % of tasks where pytest passes on attempt 1 — if this grows project-over-project, system is generalizing
- MATG (Mean Attempts to Green): avg retries when first attempt fails — if this drops, RAG flywheel is compounding
- Thompson Exploitation Shift: as arms converge, exploitation ratio rises — mathematical proof from thompson_state.json
- Training triad: fine-tune on (State + Reflection + Action), not just accepted patch — otherwise Qwen becomes autocomplete bot
- VPS reality: can't run Qwen2.5-7B on 2GB RAM — host on RunPod/Modal via API (same call as DeepSeek)

### Claude Evaluation

**ACCEPTED:**
- ZSPR + MATG: correct metrics. These are the two numbers that answer a VC or a viva skeptic.
- Thompson Exploitation Shift: strongest answer to "fancy caching" charge because it's mathematical — Beta distribution variance is measurable from thompson_state.json
- Training triad: Gemini's most important point. Training on final patch only = autocomplete bot. Training on reasoning trajectory = agent. This is correct.
- VPS check: already known and locked in CLAUDE.md. Option A (serverless GPU) is already v4.0 plan.

**CAVEAT on training triad:**
The <think> block doesn't exist in Agent-X prompts yet (listed as CoT fix in v41_creation_fixes.md).
We cannot capture the reflection layer until it exists.
This means CoT prompt is now a v4.0 PREREQUISITE, not just a speed improvement.
Order is locked: add <think> → store in memory.jsonl → THEN fine-tune.
Without this order: fine-tuning at 500 entries produces the autocomplete bot Gemini warned about.

**New field needed when CoT is built:**
memory.jsonl MemoryEntry needs: `think_block: str = ""`
Capture the <think> content alongside patch_applied.
This is the training signal that makes fine-tuning worthwhile.

### What Gemini Missed

**Gap 1 — BM25 precision at scale (5,000+ entries)**
At 5,000 entries more documents match the same keywords.
BM25 retrieval precision drops as corpus grows.
Gemini said nothing about this. The ranked verbosity approach (ChatGPT Review, RAG section) is partial answer.
Full answer: unknown. Follow-up question queued.

**Gap 2 — Thompson arms multiplicity problem**
At 100+ projects: some arms have 200 data points, some have 1.
A Beta(1,1) prior on a rarely-seen arm scores it at 50% — artificially equal to a proven arm.
Gemini ignored this. Already partially logged in memory/project_thompson_limits.md.
Real fix: hierarchical prior or minimum arm age gate (20+ runs before Thompson score trusted).

**Gap 3 — Training data quality vs quantity**
Not all 500 accepted entries are equal:
  - Some fixed trivial tests (5 lines, obvious fix) → low signal
  - Some fixed real multi-file logic (50 lines, 3 retries) → high signal
Gemini said "train on accepted entries" but gave no quality filter.
Fine-tuning on unweighted data degrades the model.
Quality signal candidates: retry_count, patch line count, test complexity, bug_signature novelty.
Follow-up question queued.

### Final Decision
- Add ZSPR + MATG as tracked metrics to progress.md and CLAUDE.md
- CoT <think> block is now v4.0 prerequisite — update v41_creation_fixes.md
- Add think_block field to MemoryEntry schema when CoT is built
- Log Thompson exploitation ratio per project cohort (not just globally)

### Impact
- ZSPR + MATG give us the proof artifact for any viva or pitch
- Training triad dependency means we can't fine-tune before CoT is built
- Thompson exploitation shift is the strongest mathematical counter to "it's just a cache"

---

---

## REVIEW 2 — BM25 at Scale + LoRA Data Curation (2026-03-27)

**Topic:** Scaling retrieval precision and training data quality

### Input (Gemini)
- BM25 at scale: ranked verbosity solves token bloat but NOT retrieval precision
- Fix: Two-Stage Lexical Pipeline:
    1. Hard filter by error_type/affected_file before BM25 runs (O(1))
    2. Field-weighted scoring: bug_signature match = 3x, test_summary = 1x
- LoRA pruning tiers:
    - Tier 1 (KEEP): retry_count==0 AND patch > 5 lines — zero-shot triumphs
    - Tier 2 (KEEP SOME): retry_count 1-2 AND good <think> block
    - Tier 3 (DROP): retry_count >= 3 — toxic, teaches guessing
    - Tier 4 (DROP): patch < 3 lines — trivial noise
- "50 high-quality reasoning traces outperform 5,000 garbage ones"
- ZSPR baseline: check retries_used in memory.jsonl now

### Actual Numbers (calculated 2026-03-27 from memory/memory.jsonl)
```
Total entries:       605
Accepted:            345
retries_used=0:      335  (97.1% ZSPR — see caveat below)
retries_used=1:        2
retries_used=2:        8
retries_used=3+:       0
lines_changed < 3:   276  (trivial — Tier 4 DROP)
lines_changed >= 5:   46  (solid — Tier 1 KEEP)
<think> blocks:        0  (CoT not built yet — Tier 2 empty)
```

### Claude Evaluation

**ACCEPTED — BM25F + Hard Filter:**
Hard filter by failure_category before BM25 runs — already have this field.
Field-weighted scoring in _score_entries() — 15 lines change to similarity.py.
Zero new RAM. Zero new libraries. Correct fix.

**ACCEPTED with critical caveat — Pruning tiers:**
The tiers are correct. But the 97.1% ZSPR is a red flag, not a celebration.

97.1% ZSPR means the 345 entries are almost all from the CI repair pipeline
running on the same 5 synthetic fixtures (syn_001..005) — same 5 bugs, different
parameters, repeated. This is memorization, not generalization.

Apply Tier 4 filter (lines < 3 → DROP): 276 entries gone.
Real training-ready entries today: ~46. Not 345.

Tier 2 (retry + <think>): empty — CoT prompt not built yet. Gated on FIX-9.
Tier 3 (retry >= 3 → DROP): empty — system never hit max retries on accepted entries.

**ACCEPTED — "50 quality traces > 5,000 garbage":**
We are almost at 50 usable entries (46 with lines >= 5).
But ALL 46 are from synthetic fixtures. Not real project diversity.
Fine-tuning on synthetic-only data teaches the model the 5 known bugs, not the pattern class.

### What the ZSPR number actually means
- ZSPR = 97.1% on synthetic fixtures: memorization, not generalization
- ZSPR on real projects: unmeasured — creation mode too new
- Real ZSPR baseline: will emerge from first 10 real projects via v4.1

This is actually stronger for a viva: "I know exactly why this number doesn't prove generalization, and here is my measurement plan." Intellectual honesty is more convincing than a suspicious 97%.

### Final Decision
- BM25F: add hard filter + field weighting to similarity.py — schedule as FIX-10 after Tier 1 fixes
- Training tiers: log and apply when memory.jsonl has 50+ real-project entries (not synthetic)
- ZSPR baseline: synthetic = 97.1% (logged). Real project baseline = measure after 10 real projects.
- CoT (<think>) remains prerequisite before Tier 2 training data exists

### Impact
- Ranked verbosity (ChatGPT suggestion) + hard filter + field weighting = three-layer precision stack
- LoRA gate is no longer "500 entries" — it's "50 real-project entries with <think> blocks"
- The viva answer on ZSPR is now honest and stronger than the raw number alone

---

## REVIEW 3 — BM25 at Scale: Two-Stage Pipeline (2026-03-27)

**Topic:** Q1 follow-up — minimum architecture change to maintain BM25 precision at 5,000+ entries

### Input (Gemini)
- "Ranked Verbosity" is a context window optimization trick, NOT a retrieval precision fix
- At 5,000 entries, BM25 hits "Keyword Soup" — 400 entries all contain `FastAPI`, `CORS`, `Error`
- Fix: Two-Stage Retrieval Pipeline
- **Approach A (BM25F):** Field-weighted scoring — `error_traceback` match = 5x, `code_comments` = 1x
- **Approach B (LLM Re-Ranker):** BM25 grabs Top 20 → DeepSeek 200-token judge picks exact match
- Verdict: Approach B is the correct architectural fix

### Claude Evaluation

**ACCEPTED — Ranked Verbosity critique:**
Correct. Ranked verbosity optimizes token budget after retrieval. It does nothing to fix which
entries BM25 fetches. If BM25 returns wrong top-5, ranked verbosity delivers one detailed wrong
answer and four abbreviated wrong answers. Precision must be fixed upstream of prompt assembly.

**ACCEPTED with hard caveat — Approach A (BM25F):**
Field-weighted scoring math is correct and the right direction.
Critical gap Gemini missed: `rank_bm25` library does NOT ship BM25F natively.
Available variants: BM25Okapi, BM25Plus, BM25L — not fielded BM25.
This requires a custom implementation (~30 lines), not a config change.
Still the right fix. Just more work than "upgrade to BM25F."

**PARTIALLY ACCEPTED — Approach B (LLM Re-Ranker):**
Pattern is architecturally correct and industry-standard.
But the "200-token prompt" claim is wrong. 20 summaries × ~80 tokens each = ~1,600 tokens
input per retrieval call. Every memory lookup = one DeepSeek API call.
Currently: memory retrieval costs zero API calls (pure local BM25).
At 5,000 entries with frequent failures: significant API cost and latency added to every error.

**What Gemini missed — Hard Filter (FIX-10, already planned):**
Filter by `failure_category` before BM25 runs — O(1), zero API cost, zero RAM.
`failure_category` field already exists in memory.jsonl.
A CORS error only searches CORS entries. 400 matches → 40 matches before BM25 even runs.
This solves keyword soup at the cheapest possible layer. Gemini never mentioned it.

### Correct Build Order (locked)
```
Layer 1 — Hard filter by failure_category    O(1), zero cost     ← FIX-10 already planned
Layer 2 — BM25F field weighting              ~30 lines, zero RAM ← Approach A (custom impl)
Layer 3 — LLM Re-Ranker                      API cost, fallback  ← Approach B, only if L1+L2 insufficient
```
Do NOT jump to Layer 3 before Layer 1 and 2. Hard filter + BM25F solves the problem for free.
LLM re-ranker is the nuclear option for 50,000+ entries, not 5,000.

### What Gemini Missed
- rank_bm25 has no native BM25F — requires custom implementation
- "200-token prompt" is wrong — 20 summaries ≈ 1,600 tokens input minimum
- Hard filter (FIX-10) was already planned and eliminates most of the keyword soup at O(1)
- Approach B trades zero-cost retrieval for API cost on every single error lookup

### Final Decision
- Ranked Verbosity: keep as token budget optimization only — label it correctly in code/docs
- Layer 1 (Hard filter): already FIX-10, schedule after Tier 1 fixes — highest ROI
- Layer 2 (BM25F custom): implement after hard filter confirmed working — ~30 lines in similarity.py
- Layer 3 (LLM Re-ranker): park until 50,000+ entries — revisit at v5.0
- Three-layer label: ranked verbosity + hard filter + BM25F = full precision stack at 5,000 scale

### Impact
- Keyword soup at 5,000 entries: solved by hard filter + BM25F alone
- Zero new RAM, zero new libraries (BM25F is custom on existing rank_bm25 base)
- LLM re-ranker deferred — keeps retrieval at zero API cost
- Ranked Verbosity correctly classified: prompt formatting, not retrieval architecture

---

## FOLLOW-UP QUESTIONS FOR GEMINI (not yet asked)

### Q1 — BM25 at scale
ANSWERED — see REVIEW 3 above (2026-03-27)

### Q2 — Training data quality
ANSWERED — see REVIEW 4 below (2026-03-27)

---

## REVIEW 4 — LoRA Training Data Quality: Signals, Weighting, Synthetic CoT (2026-03-27)

**Topic:** Q2 follow-up — quality signals inside Tier 1, weighting vs filtering, <think> block gap

### Input (Gemini)
- Signal A: Bug Signature Novelty — cluster by failure_category, keep top 2 per cluster
- Signal B: Test-to-Implementation Ratio — if src/ lines < 3 but tests/ lines = 20, downgrade
- Signal C: Thompson Arm Surprise — low-prior arm succeeded zero-shot = Golden Signal
- LoRA: do NOT use custom loss weighting — hard filter + oversampling instead
- Oversampling hack: duplicate elite entries 3x in .jsonl to increase weight naturally
- Synthetic CoT: feed 46 (State + patch) pairs to Claude 3.5 Sonnet → backfill <think> blocks
- Verdict: hard filter to ~20 elite entries + synthetic CoT → valid training triplets today

### Claude Evaluation

**ACCEPTED — Signal A (Bug Novelty / Dedup):**
Correct. Top 2 per failure_category prevents import-error over-indexing.
46 entries with 15 ImportError variants → model learns one fix class too well.
Dedup by failure_category is the right first cut.

**ACCEPTED with caveat — Signal B (Test-to-Implementation Ratio):**
Logic is sound. But patches are unified diffs — parsing src/ vs tests/ line counts
requires a small extractor function, not just reading the existing lines_changed field.
lines_changed today is a single integer (total). Needs splitting by path prefix to apply this signal.
~10 lines to implement. Correct direction.

**ACCEPTED with caveat — Signal C (Thompson Arm Surprise):**
Correct in principle — low-prior arm that succeeded zero-shot = high information gain.
Hard dependency: requires confidence-at-selection-time stored in memory.jsonl.
If thompson_arm_scores stores arm name only (not score at time of pick), this signal
is not computable without re-deriving from thompson_state.json per entry.
Verify field contents before implementing. May require a backfill script on existing entries.

**ACCEPTED — Hard Filter + Oversampling (no custom loss weights):**
"Don't touch cross-entropy weights" is correct. Loss weight modifications on causal LMs
destabilize learning rate and rarely improve over clean data.
Oversampling caveat: at 46 entries, duplicating one entry 3x = 6.5% of training data
is one example. Severe overfitting risk at this scale. Cap oversampling at 2x max
until dataset reaches 200+ real entries.

**PARTIALLY ACCEPTED — Synthetic CoT Bootstrapping:**
The idea is genuinely valuable. Backfilling <think> blocks on existing accepted entries
is better than waiting for live CoT captures.
Critical flaw Gemini missed: Gemini said "use Claude 3.5 Sonnet."
Our Agent-Y uses deepseek-reasoner. If <think> blocks are generated by Claude,
fine-tuned Qwen learns Claude's reasoning style, not DeepSeek's.
Distribution mismatch → model behaves like Claude at inference, not like our pipeline.
Fix: use deepseek-reasoner for backfilling — same model family as the target.

Second flaw: retrospective rationalization ≠ genuine reasoning trace.
Any model explaining a known patch is rationalizing, not reasoning.
Signal quality: synthetic CoT < live <think> captures. Still better than no CoT.
Use synthetic CoT as bootstrap only — replace with live captures as they accumulate.

### What Gemini Missed

**The diversity gap — biggest problem, never mentioned:**
All 46 Tier 1 entries are from 5 synthetic fixtures (syn_001..005).
Even perfectly curated + synthetic CoT backfilled → training on 5 bug types.
Hard filter to 20 elite entries + oversampling = 20 elite examples of the same 5 bugs.
Real generalization requires real project diversity.
The bootstrapper is useful but doesn't solve the fundamental diversity problem.
Gate remains: 50 real-project entries WITH <think> blocks — not 46 synthetic ones.

### Locked Decisions (updated)
- Quality signals: failure_category dedup → test/impl ratio → Thompson surprise (in that order)
- LoRA: hard filter to ~15-20 elite entries, no custom loss weights, 2x oversampling max
- Synthetic CoT: use deepseek-reasoner (NOT Claude) to backfill 46 entries
- Synthetic CoT is bootstrap only — replace with live <think> captures from real projects
- LoRA gate unchanged: "50 real-project entries WITH <think> blocks" — synthetic fixture entries do not count toward this gate
- Build synthetic bootstrapper ONLY after 10 real projects exist — fixture-only training is premature

### Impact
- Three quality signals now defined and ordered: novelty > test/impl ratio > Thompson surprise
- Hard filter target: ~15-20 entries from 46 (after dedup + ratio filter)
- Synthetic CoT is viable with right model (deepseek-reasoner) — unblocks training data format
- Oversampling capped at 2x to prevent micro-dataset overfitting
- Diversity gap acknowledged: bootstrapper ≠ real generalization proof

### Q3 — Thompson arms at scale (ask separately)
ANSWERED — see REVIEW 5 below (2026-03-27)

---

## REVIEW 5 — Thompson Sampling at Scale: Empirical Bayes + Decay (2026-03-27)

**Topic:** Q3 follow-up — preventing fresh arm over-sampling at 40+ arms without heavy libraries

### Input (Gemini)
- Options 1 (Hierarchical Prior) + 3 (Age Gate) are "mathematically hostile" — age gate silences the prior
- Options 1 + 2 (Decay) are perfectly compatible — prior handles birth, decay handles aging
- Fix: Empirical Bayes Prior — new arm initializes at category average, not Beta(1,1)
- Formula: α_prior = total_successes / N_arms, β_prior = total_failures / N_arms
- Beta Decay: every update → α_new = (α_old × γ) + (1-γ), γ = 0.95
- Drop the Age Gate (Option 3) — redundant once EB prior is live
- Zero heavy libraries, O(n_arms), pure Python arithmetic

### Claude Evaluation

**PARTIALLY ACCEPTED — Options 1+3 conflict:**
Conflict is real but "mathematically hostile" is overstated. They operate at different lifecycle
stages: prior handles initialization quality, age gate handles trust threshold.
The practical problem: once EB prior is live, age gate becomes redundant, not hostile.
Correct action: keep age gate until EB prior is implemented and validated, then remove it.
Do not drop age gate preemptively.

**ACCEPTED with math caveat — Empirical Bayes Prior:**
Direction is correct. New arms should start at category average, not Beta(1,1).
Formula given (total/N_arms) is a category-average heuristic, not precise Empirical Bayes.
True EB uses Method of Moments on observed per-arm success rates to estimate hyperparameters.
At ≤40 arms: the approximation is fine in practice — call it what it is, not "Empirical Bayes."
Hard dependency: requires failure_category → arm mapping in thompson_state.json.
Verify this mapping exists before implementing. May require a state schema change.

**ACCEPTED with two bugs — Beta Decay γ=0.95:**
Decay direction is correct. Formula is mostly right. Two bugs:

Bug 1 — Decay per-update ≠ decay per-time:
Formula applied per selection event means a popular arm (100 selections) decays
10× more than a rare arm (10 selections). Popular arms punished for being popular.
Fix: apply decay once per project completion, not per selection event.

Bug 2 — Floor creates bimodal prior:
(1-γ) = 0.05 → floor is Beta(0.05, 0.05) — bimodal U-shaped distribution.
Worse than Beta(1,1) as a floor. Model becomes maximally uncertain at floor.
Fix: clamp floor to max(α, 1.0) and max(β, 1.0) after every decay step.

### Locked Implementation (corrected)
```python
# Empirical Bayes initialization (new arm in category):
category_arms = [arms in same failure_category]
α_prior = mean([a.alpha for a in category_arms]) or 1.0
β_prior = mean([a.beta  for a in category_arms]) or 1.0
new_arm = Beta(α_prior, β_prior)

# Decay — applied once per project completion, NOT per selection:
γ = 0.95
for arm in all_arms:
    arm.alpha = max(arm.alpha * γ + (1 - γ), 1.0)  # floor at 1.0
    arm.beta  = max(arm.beta  * γ + (1 - γ), 1.0)  # floor at 1.0
```

### What Gemini Missed
- Decay per-update vs per-project asymmetry — punishes popular arms unfairly
- Floor value Bug(0.05, 0.05) creates bimodal prior worse than Beta(1,1)
- Category-to-arm mapping dependency in thompson_state.json — may need schema change
- None of this is needed until 20+ arms exist — current scale is <10 arms, <50 runs

### Build Gate (locked)
Do NOT implement until: real_projects >= 10 AND n_arms >= 20
Current state: 0 real projects, <10 arms → existing age gate is sufficient
Schedule: v4.0, after FIX-1 through FIX-9 complete

### Final Decision
- Empirical Bayes prior: APPROVED for implementation at gate
- Decay γ=0.95 per project completion + floor clamp: APPROVED for implementation at gate
- Age gate (20 runs): KEEP until EB prior validated on 10+ real projects, then remove
- "15-line Python update function" offer: DEFERRED — premature, gate not met

---

## VIVA PREP — QUESTIONS TO KNOW COLD

These are the hard questions a skeptic will ask. Know these answers before any defense.

**Q: "You built a cache, not a learner. Prove it's generalizing."**
A: ZSPR trajectory is the proof — not the current number. Current ZSPR is 97.1% on
5 synthetic fixtures (same bugs repeated). That's memorization and I know it.
The real test: ZSPR on 10 diverse real projects built by v4.1. A cache has flat ZSPR
across project types. A learning system extrapolates — ZSPR on a never-seen project type
stays high because the Skill Vault generalizes patterns, not bug instances.
The measurement plan exists. The synthetic baseline is logged. That's the honest answer.

**Q: "Your 97.1% ZSPR sounds too good to be true."**
A: It is. 345 accepted entries, 276 under 3 lines — trivial patches from 5 synthetic repos.
After Tier 4 pruning (lines < 3 → drop) the real training-usable set is 46 entries.
The system learned the 5 fixture bugs very well. Real generalization starts measuring
when real projects run. First 10 real projects are the real baseline.

**Q: "Thompson Sampling is overkill. A frequency table would do the same thing."**
A: A frequency table gives the most-used strategy. Thompson Sampling gives the best-performing
strategy under uncertainty. When you have 2 data points on a new error type, frequency table
picks the first one tried. Thompson explores (tries the uncertain one) then exploits (locks in
the winner). The exploration phase is the difference.

**Q: "Your memory.jsonl is poisoned by bad patches that barely passed trivial tests."**
A: Valid concern. Accepted-only filter is the first gate. Second gate: retry_count as quality
signal — a patch accepted on attempt 3 after two rejections is stronger signal than one
accepted on attempt 1 on a 3-line test. Third gate (v4.0): quality score before fine-tuning.
We know the gap. It's scheduled.

**Q: "Why BM25? Embeddings are objectively better at semantic search."**
A: On a 2GB VPS, sentence-transformers was 800MB RAM — OOM risk with everything else running.
BM25 uses <10MB. The constraint is not ignorance — it's engineering for production.
At 5,000 entries we revisit. Until then, BM25 on error tracebacks is mathematically sound
because error messages are keyword-dense, not semantically subtle.

**Q: "DeepSeek will be deprecated. Your whole system dies."**
A: DeepSeek is called via OpenAI-compatible API. Swap base_url and model name — pipeline
unchanged. The system is model-agnostic by design. The fine-tuned Qwen is the exit from
API dependency entirely.

**Q: "Why sequential? Every serious agent system uses parallelism."**
A: 1 vCPU. Parallel pytest = file lock crashes. Parallel API calls = race conditions on
state.json. Sequential on a constrained machine is not a limitation — it's the only design
that doesn't crash in production. Competitors with cloud budgets can parallelize. We ship.

---

---

## REVIEW 6 — Blast Radius Containment + AST Pre-Flight (2026-03-27)

**Topic:** Plan efficiency required to survive DeepSeek hallucination at scale

### Input (Gemini)
- Save State Architecture: treat every 5-10 tasks as isolated milestone, roll back on failure
- Context Pruning: need-to-know only — global_interfaces signatures not full files
- Template Cheat Sheet: DeepSeek only writes unique business logic, not boilerplate
- AST Pre-Flight Check: ast.parse() + import validation before pytest runs
- Verdict: 60-70% success rate on 30-file project is realistic with guardrails

### Claude Evaluation

**ACCEPTED — Save State / Milestone rollback:**
Correct concept. Already planned as FIX-13 (Iteration Audit Gate).
Gemini's mechanism "roll back to save state" left unspecified.
The mechanism is free and already in our stack: git tag per milestone.
  Milestone 1 passes audit → git tag milestone-1
  Milestone 2 fails catastrophically → git reset --hard milestone-1
Zero new infrastructure. Add git tag step to FIX-13 scope.

**ACCEPTED — Context Pruning:**
global_interfaces AST mapper (FIX-1) already does exactly this.
Signatures only, not full files. Gemini validated our existing design.

**ACCEPTED — Template Cheat Sheet:**
Identical to FIX-3b already planned. Direction confirmed.

**ACCEPTED with caveat — AST Pre-Flight Check:**
ast.parse() before pytest is correct and cheap. Zero RAM. Zero API cost.
Enhances FIX-9 (placeholder detection) — complementary, not competing:
  FIX-9 (current):    regex catches TODO/pass placeholder stubs
  AST pre-flight:     ast.parse() catches syntax errors (gate 1)
                      import check against global_interfaces (gate 2)
  pytest:             logic correctness (gate 3, unchanged)

Caveat Gemini missed: import validation requires global_interfaces populated.
Task 1 has empty global_interfaces — cannot validate imports for first task.
  Task 1:  skip import validation (global_interfaces empty)
  Task 2+: validate imports against global_interfaces from previous tasks
Add sequencing guard before import check.

**REJECTED — "Attention dilution" mechanism:**
Conclusion (keep context lean) is correct.
Mechanism description is wrong. Transformers don't linearly dilute attention.
Real issue: positional weighting — distant context gets less weight than recent.
Lean prompts work because less surface area for error, not "dilution."

### What Gemini Missed
- git tag as the save state mechanism — free, already in our stack
- Task 1 import validation impossible (empty global_interfaces) — sequencing bug
- AST pre-flight is gate 1, pytest is gate 2 — both needed, neither replaces the other
- 0.9^55 math was already in our analysis — Gemini rediscovered it

### Locked Decisions
- FIX-9 scope expanded: ast.parse() syntax check + import validation against global_interfaces
  sequencing: skip import check on task 1, enable from task 2 onward
- FIX-13 scope expanded: git tag per milestone after audit passes
  rollback: git reset --hard <milestone-tag> on catastrophic failure
- Code generation offer: DEFERRED — analysis phase only

---

## HOW TO USE THIS FILE

1. Before any viva/pitch: read VIVA PREP section cold
2. When Gemini gives a new review: add it here with full Claude evaluation
3. Follow-up questions go in the FOLLOW-UP section until asked
4. Once asked: move response into a new REVIEW block

Rule: Gemini = stress-tester. Claude = filter + integrator. This file = why we built it this way.


---

## INSIGHT — Multi-Agent Architecture is a Prompt Engineering Problem (2026-03-28)

**Origin:** B2 (STATE_PATH) research session — 3 models gave 3 different answers, human adjudicated.

### What happened
- Perplexity Sonnet: state inside .agent/ (good answer)
- ChatGPT o4: same + one extra guard (additive)
- Gemini 2.5 Pro: opposite — state outside memory/{slug}/ (contradicted both, but RIGHT for our constraints)
- Claude: adjudicated manually → Gemini wins because of git clean -fd rollback rule

### The insight
Multi-agent "debate" architecture (4 agents arguing) is:
- Expensive (4 API calls vs 1)
- Non-deterministic (models contradict each other)
- Still requires human adjudication to resolve conflicts
- NOT autonomous

The value wasn't the 3 models. The value was the PROCESS:
  bug described → failure modes found → production systems checked → verdict for OUR constraints → spec written

That process = a prompt engineering problem, not a multi-agent problem.

### Locked decision
One DeepSeek call with a structured prompt:
  1. Here is the bug
  2. What are the failure modes?
  3. What do production systems do?
  4. What is the verdict for OUR specific constraints?
  5. Write the spec.

Same reasoning. No arguments. No adjudication. One call.

### Training data implication
These research sessions (bug + 3-model research + adjudication + final spec) =
the real LoRA training set. Not accepted patches — accepted ARCHITECTURAL DECISIONS with reasoning.

Format:
  input:  bug description + system constraints
  <think>: the research + failure mode analysis + production system comparison
  output: the final spec (exact format of v41_creation_fixes.md)

This trains DeepSeek to reason like a staff engineer, not just autocomplete code.
Gate: same as LoRA gate — 50 real-project entries with <think> blocks.

### Why this matters
memory.jsonl today = accepted patches (code level)
This training set = accepted architectural decisions (system design level)
Combined = model that can both DESIGN and BUILD

That is the real moat. Nobody else has this training data.
