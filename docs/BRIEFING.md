# Agent-XYZ | SESSION BRIEFING
# One file. Full picture. No code reading required.
# Last updated: 2026-03-27
# Read this BEFORE touching any code or any other doc.

---

## WHAT THIS SYSTEM IS

Autonomous software engineer. User drops a brief.yaml → Agent-Y plans → Agent-X builds
→ tests pass → working git repo out. Runs on a $16/mo VPS. Proven end-to-end.

```
brief.yaml (idea)
     ↓
Agent-Y (DeepSeek-reasoner) — stateless planner, reads SharedState, outputs Plan + Tasks
     ↓
Orchestrator — dumb loop, zero intelligence, enforces order
     ↓
Agent-X (DeepSeek-chat) — writes files, runs pytest, fixes errors, reports done/failed
     ↓
working git repo (pushed to GitHub after every task)
```

---

## WHAT EXISTS TODAY (do not re-audit — trust this)

**Tests:** 657 passing (2026-03-27). Zero failures.
**Pipeline:** 20-stage CI repair pipeline (phase1 + phase2) — COMPLETE, battle-tested.
**Creation mode:** Agent-Y + Agent-X + Orchestrator loop (phase3) — COMPLETE, proven on simple tasks.
**Memory:** 605 entries in memory.jsonl. 345 accepted. BM25 + Thompson hybrid retrieval. LIVE.
**Skill Vault:** Beta(α,β) Thompson Sampling on reusable code patterns. LIVE.
**Interfaces:** Telegram bot, Streamlit dashboard, brief_watcher (watchdog). ALL LIVE.
**VPS:** DigitalOcean $16/mo, 2GB RAM, 1 vCPU, 70GB SSD. Sequential only.

**What works end-to-end:**
Drop brief.yaml → run_loop() → working repo in ~12 seconds (proven on simple 1-file projects).

**What doesn't work yet:**
Real multi-file projects (FastAPI app, Telegram bot, CLI tool). 9 specific gaps block this.
All gaps are documented. None require architecture changes.

---

## THE 9 GAPS (creation mode — what blocks real projects)

Full analysis: @docs/prompts/v41_creation_fixes.md

Priority order — execute exactly this sequence, one at a time:

```
TIER 1 (fix first — breaks every real project):
FIX-1: global_interfaces not injected into Agent-X prompt          — 5 lines
FIX-2: pip install missing before pytest                           — 10 lines
FIX-3: scaffold task T0 not implemented (stub-driven development)  — 30 lines

TIER 2 (fix after Tier 1):
FIX-4: requirements.txt never generated in plan                    — prompt change
FIX-5: plan_goal() ignores context.md on resume                   — 10 lines
FIX-6: replan() fires with empty failed_diff                       — 15 lines

TIER 3 (fix after Tier 2):
FIX-7: file_edit sends raw text not unified diff                   — 30 lines
FIX-8: resolve_safe_path() missing on some writes                  — audit
FIX-9: placeholder code reaches pytest undetected                  — 15 lines
```

Say "step FIX-N" → read docs/prompts/v41_creation_fixes.md → execute that fix only → run full pytest → stop.

---

## KEY ARCHITECTURAL DECISIONS (locked — never relitigate)

| Decision | What | Why locked |
|----------|------|------------|
| Sequential only | One project at a time | 1 vCPU — parallel = file lock crashes + state race |
| BM25 not vector DB | rank_bm25 for retrieval | sentence-transformers = 800MB RAM OOM on 2GB VPS |
| DeepSeek-chat | Code generation | OpenAI-compatible API — swap base_url to change model |
| 50/15 line limits | write_file=50, file_edit=15 | Forces task decomposition — raising hides bad plans |
| uv always | Dependency management | Global package cache — no per-project venv bloat |
| Test first | Tests before implementation | Truth signal — code that proves it works, not appears to |
| Shadow branches | agent-x/fix-<run_id> | main is sacred — never touched |

---

## HARD RULES (no exceptions — enforced by hooks)

1. confidence < 0.85 → observer mode, pipeline stops
2. patch > 15 lines → sanitiser rejects, retry with different prompt
3. max 3 retries — each retry prompt MUST differ (rejection reason injected)
4. ALWAYS write to memory.jsonl regardless of outcome (finally: block)
5. resolve_safe_path() on EVERY file write — no exceptions
6. Orchestrator atomic write: state_tmp.json → rename (never direct json.dump)
7. Agent-Y called ONLY when: plan empty OR failed_task_streak == 2
8. No secrets in code — os.environ inside functions only, never module level
9. No cross-imports between phase1/ phase2/ phase3/
10. Claude NEVER commits, NEVER pushes — user commits manually

---

## WHAT WAS LEARNED THIS SESSION (2026-03-27)

**BM25 is live:** rank_bm25 was installed. 657 tests passing. The Jina removal is complete.

**ZSPR reality check:**
- Measured ZSPR = 97.1% (335/345 accepted entries had zero retries)
- This is NOT proof of generalization — it's synthetic fixture memorization
- 345 accepted entries → 276 are trivial (<3 lines, Tier 4 DROP for training)
- Real training-ready entries: ~46 (lines >= 5 from diverse inputs)
- LoRA gate revised: NOT "500 entries" — "50 real-project entries WITH <think> blocks"

**CoT is now v4.0 prerequisite:**
The <think> block (reasoning before code) must be built BEFORE fine-tuning.
Training on accepted patches alone = autocomplete bot.
Training on (state + <think> reasoning + accepted patch) = real agent.
Add <think> → capture in memory.jsonl → THEN fine-tune Qwen.

**BM25 precision stack locked (Gemini Reviews 3+4+5):**
Three-layer stack for 5,000+ entries (all gated — do not build before FIX-9 done):
  L1: hard filter by failure_category — O(1), zero cost — FIX-10 queued
  L2: BM25F field weighting — custom impl ~30 lines (rank_bm25 has no native BM25F)
  L3: LLM re-ranker — deferred to v5.0 / 50k+ entries only
Ranked Verbosity = token budget trick only, NOT retrieval precision fix.

**LoRA quality signals locked:**
  Tier 1 KEEP: retry=0 AND lines >= 5 (46 entries today — all synthetic)
  Signal order: failure_category dedup → test/impl ratio → Thompson surprise
  Hard filter to ~15-20 elite entries. 2x oversampling max (not 3x — overfitting risk).
  Synthetic CoT backfill: use deepseek-reasoner (NOT Claude) — distribution match.
  Gate unchanged: 50 real-project entries WITH <think> blocks before LoRA.

**Thompson Sampling at scale locked:**
  Empirical Bayes prior: new arm initializes at category average (not Beta(1,1))
  Decay γ=0.95: applied per project completion (NOT per selection event)
  Floor: max(α, 1.0) and max(β, 1.0) — prevents bimodal prior at floor
  Age gate: keep until EB prior validated on 10+ real projects, then remove
  Build gate: real_projects >= 10 AND n_arms >= 20

**Viva metrics established:**
- ZSPR (Zero-Shot Pass Rate): synthetic baseline 97.1% — real baseline TBD after 10 real projects
- MATG (Mean Attempts to Green): currently ~1.02 (almost all zero-shot on synthetic)
- Thompson Exploitation Shift: measure exploitation/exploration ratio per project cohort

---

## AGENT BEHAVIOR SPEC
Full behavioral contract — how Agent-XYZ runs every project end-to-end:
@docs/AGENT_BEHAVIOR.md ← read this before touching any loop/orchestrator/telegram code

---

## KEY FILES (where things live)

```
docs/BRIEFING.md              ← YOU ARE HERE — read first every session
docs/progress.md              ← test counts + build history
docs/session_prompts.md       ← active queue + what to do next
docs/prompts/v41_creation_fixes.md ← full analysis of 9 gaps + tier breakdown
docs/gemini_reviews.md        ← Gemini stress-tests + Claude evaluation + VIVA PREP
docs/chatgpt_reviews.md       ← ChatGPT architecture reviews (all accepted)
docs/v30_open_questions.md    ← open bugs (Q1-Q5 all fixed)
docs/problems_and_solutions.md ← original P1-P26 issues (P1-P23 fixed)
CLAUDE.md                     ← hard rules + pipeline spec + upgrade queue
```

---

## VIVA / PITCH QUESTIONS — KNOW THESE COLD

**"You built a cache, not a learner."**
ZSPR trajectory is the proof — not the current number. Current 97.1% is on 5 synthetic
fixtures. Real proof: ZSPR on 10 diverse real projects. A cache has flat ZSPR across
project types. A learning system stays high on never-seen patterns via Skill Vault generalization.

**"Your 97.1% is too good to be true."**
It is. 276 of 345 entries are trivial (<3 line patches) from the same 5 synthetic repos.
Tier 4 pruned: 46 real training entries. I know this. The measurement plan for real generalization
uses the first 10 real projects built by v4.1.

**"Why BM25? Embeddings are better."**
On 2GB VPS, sentence-transformers = 800MB OOM. BM25 = <10MB. Error tracebacks are
keyword-dense, not semantically subtle. At 5,000+ entries: add field-weighted BM25F.
Revisit embeddings at v5.0 when model is fine-tuned and can self-embed.

**"Why sequential? Real agent systems parallelize."**
1 vCPU. Parallel pytest = file lock crashes. Parallel API = state.json race conditions.
Sequential on constrained hardware is not a limitation — it's the only design that
doesn't crash in production. Competitors with cloud budgets parallelize. We ship.

**"DeepSeek will be deprecated. Your system dies."**
No. OpenAI-compatible API. Change base_url + model name. Pipeline unchanged.
The fine-tuned Qwen (v4.0) is the exit from API dependency entirely.

**"What's your moat?"**
memory.jsonl. 605 execution traces, growing every run. Training data nobody else has.
When fine-tuned on this data: model knows our stack, our patterns, our error classes.
Runs locally. Zero API cost after training. Nobody can buy this data — it has to be earned.

---

## WHAT NOT TO DO (Claude-specific rules)

- Do NOT re-audit v30_creation_steps.md from scratch — it's done
- Do NOT suggest parallel execution — VPS constraint, locked
- Do NOT suggest vector databases — BM25 is the decision, locked
- Do NOT suggest raising the 50/15 line limits — architectural gate, locked
- Do NOT suggest Obsidian integration — parked at v4.2
- Do NOT commit or push — user commits manually after review
- Do NOT start next fix until all tests pass for current fix
- Do NOT read code files unless a specific fix requires it — trust the docs

---

## SESSION START PROTOCOL

1. Read this file (BRIEFING.md) — done
2. Read docs/session_prompts.md — find next PENDING step
3. Ask user: "Ready to start FIX-N?" — wait for confirmation
4. Read the relevant FIX section in docs/prompts/v41_creation_fixes.md
5. Execute — run pytest after every file touched
6. Update docs/progress.md when done
7. Stop — do not proceed to next fix without user confirmation
