# Agent-XYZ | SESSION BRIEFING
# One file. Full picture. No code reading required.
# Last updated: 2026-03-29
# Read this BEFORE touching any code or any other doc.

---

## WHAT THIS SYSTEM IS

Autonomous software engineer. User drops a brief.yaml → Agent-Y plans → Agent-X builds
→ tests pass → working git repo out.

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

## HARDWARE (updated 2026-03-29)

Old: DigitalOcean $16/mo — 1 vCPU, 2GB RAM, 70GB SSD
New: 2 vCPU, 4GB RAM, 70GB SSD

**What this unlocks:**
- sentence-transformers/all-MiniLM-L6-v2 (90MB) — semantic skill retrieval now feasible
- Hybrid retrieval: BM25 (lexical) + embeddings (semantic), fuse scores, top-3
- Parallel iteration audit: ThreadPoolExecutor(max_workers=2) on the 6 audit checks
- Background uvicorn: spin up app, run integration tests against live localhost
- pytest-xdist -n 2: parallel tests across independent files at iteration audit

**Still off-limits:**
- Local LLMs (Qwen, Phi-3): 2.2GB+ at inference, leaves <1GB headroom — OOM risk
- Parallel codegen: sequential is a feature not a bug — state.json race conditions

---

## WHAT EXISTS TODAY (do not re-audit — trust this)

**Tests:** 657 passing. Zero failures.
**Pipeline:** 20-stage CI repair pipeline (phase1 + phase2) — COMPLETE, battle-tested.
**Creation mode:** Agent-Y + Agent-X + Orchestrator loop (phase3) — COMPLETE, proven on simple tasks.
**Memory:** 605 entries in memory.jsonl. 345 accepted. BM25 + Thompson hybrid retrieval. LIVE.
**Skill Vault:** Beta(α,β) Thompson Sampling on reusable code patterns. LIVE.
**Interfaces:** Telegram bot, Streamlit dashboard, brief_watcher (watchdog). ALL LIVE.

**Infrastructure files (all complete):**
```
brief_watcher.py       — watchdog → /projects/new/ → triggers run_loop()
state_manager.py       — atomic write (state_tmp → rename)
project_context.py     — .agent/context.md read/write
registry.jsonl         — all projects index
telegram_bot.py        — polls messages/files → run_loop()
orchestrator.py        — full task loop + FIX-1 done (global_interfaces injected)
interrupt_handler.py   — STOP/SKIP/MODIFY from Telegram, cascade_skip()
plan_checkpoint.py     — format_plan_technical/general, run_checkpoint(), 10min timer
agent_y/reasoner.py    — plan_goal(), replan(), interpret_plan_for_user()
agent_y/retrospective.py — skill extraction from successful retries
```

**What works end-to-end:**
Drop brief.yaml → run_loop() → working repo (proven on simple 1-file projects).

---

## ALL EXECUTION GAPS — CLOSED (verified via git log)

```
FIX-1   global_interfaces + AST mapper scope + SkillVault wiring                    DONE
FIX-2   pip install + surgical pytest (-x --ff + timeout tiers)                     DONE
FIX-3   scaffold T0 — stubs + __init__.py + git add                                 DONE
FIX-4   CREATION_SYSTEM_PROMPT: ALWAYS emit T1 requirements.txt                     DONE
FIX-5   read_context() before plan_goal() → resume without restart                  DONE
FIX-6   streak==2 triggers replan() with state.last_failed_diff                     DONE
FIX-7   _make_unified_diff() via difflib — FILE_EDIT always gets valid diff         DONE
FIX-8+9 _safe_repo_path() + 3 pre-write gates (placeholder/syntax/import)           DONE
AUDIT   FastAPI smoke passed + prompt fixes (POST 201, route params, requirements)  DONE
FIX-11  Plan Checkpoint: Telegram approval, user type detection, 10min timer        DONE
FIX-12  Mid-task interrupt: STOP/SKIP/MODIFY, cascade_skip, skipped in report       DONE
```

---

## REMAINING — SPECCED, NOT YET BUILT

```
FIX-3b  Template scaffold library
        match_template() before scaffold, niche-organized (crypto/stocks/bots/web/data)
        3-5 templates per niche, manifest.yaml, {{placeholder}} substitution
        ~50 lines + template directories
        Spec: @docs/prompts/v41_creation_fixes.md → FIX-3b

FIX-19  STATE_PATH multi-project isolation
        get_state_path(), write_state(), read_state() per project slug
        ProjectContext class in orchestrator, slug validation (no traversal)
        ~20 lines state_manager.py + ~15 lines orchestrator.py
        Spec: @docs/prompts/v41_creation_fixes.md → FIX-19

FIX-3c  Tiered Complexity Gates (replaces flat 50-line cap)
        complexity_gate.py: tiered limits by file type + cyclomatic complexity check
        ~40 lines new + ~5 lines mod in orchestrator.py
        Gate: after FIX-3b complete
        Spec: @docs/prompts/v41_creation_fixes.md → FIX-3c
```

---

## THE CORE ARCHITECTURAL CRITIQUE (2026-03-29)

Reviewed by Perplexity, ChatGPT, and Claude. All three independently reached the same diagnosis.

**What was built:** A highly resilient Waterfall Pipeline. Executes brilliantly. Does not adapt.

**Two root problems:**

Problem 1 — Agent-Y is blind during the build:
  Plans from brief once → executes top-to-bottom → reacts only on failure
  Never reads what was actually built → never adapts to discoveries mid-build
  If Agent-X builds something different from what was planned, downstream tasks
  still assume the original plan — imports fail, contracts break, retries waste time

Problem 2 — Memory is dark data:
  605 traces + Thompson scores exist but Agent-Y never sees them as language
  Thompson silently picks strategies but Agent-Y doesn't know why
  Makes the same class of mistakes every new project until it fails 3 times

---

## v4.2 — PROACTIVE ARCHITECTURE (next major upgrade, after gaps closed)

Three additive changes. No rebuild. ~70 lines total.

---

### Change 1 — StateDiffSummary (Observation Checkpoint)

After every successful task, Agent-X emits a structured signal. Zero LLM cost — AST diff.

```python
@dataclass
class StateDiffSummary:
    task_id: str
    what_was_planned: str          # from task.description
    what_was_actually_built: str   # 1-2 sentences, Agent-X generated
    interface_delta: list[str]     # new exports vs what Agent-Y planned
    contract_breaks: list[str]     # downstream tasks whose assumed signatures changed
    complexity_delta: int          # actual lines vs planned
    scope_creep: list[str]         # files touched outside files_to_touch
    retry_count: int               # 0=clean, 1-3=struggled
```

Materiality gate — Agent-Y wakes up only when a threshold fires:
```
contract_breaks >= 2     → re-assess downstream task acceptance criteria
retry_count avg > 1.5    → re-assess complexity budget, suggest decomposition
scope_creep detected     → flag to user, absorb into plan
complexity_delta > 1.8x  → re-estimate remaining task line budgets
nothing triggered        → continue, zero LLM call
```

Agent-Y re-assesses 2-4 times per build. Not on every task. Not only on failure.
This is replan-on-discovery. Not replan-on-failure.

---

### Change 2 — Historical Mandates (Memory Brief)

Before every plan_goal() call, synthesize memory.jsonl + Thompson history into language.
Zero LLM cost. Injected at the TOP of Agent-Y's system prompt — frames reasoning before brief.

```python
def build_memory_brief(goal: str, stack: str) -> str:
    relevant  = bm25_retrieve(goal, memory, top_k=10)
    failures  = [m for m in relevant if m["outcome"] == "fail"]
    successes = [m for m in relevant if m["outcome"] == "success"]
    skills    = skill_vault.get_top(goal, top_k=3)

    return f"""
## Historical Mandates — {len(relevant)} similar builds found

### Known failure patterns for {stack}:
# e.g. "SQLAlchemy async on SQLite: fails 6/8 builds. Use sync engine for Iter 1."
# e.g. "Missing __init__.py in tests/: 100% test discovery failure. Always scaffold it."

### High-confidence patterns (use these):
# e.g. "Skill 'jwt_auth_setup' — Beta(14,2) = 87% success. Use python-jose not PyJWT."

### Strategy history this project:
# e.g. "direct_impl tried 2x both failed. use_base_class: 1x succeeded. Prefer inheritance."

### Last similar project outcome:
# e.g. "telegram-crypto-bot (3 weeks ago): 2 iterations. Bottleneck = rate limiting."
"""
```

Agent-Y now reasons WITH history instead of the Orchestrator correcting bad choices after failure.

---

### Change 3 — Reasoning Stream to Telegram

DeepSeek-reasoner already produces <think> blocks. Currently discarded.
Forward to Telegram before the plan appears. 5-10 lines of code.

```python
# reasoner.py — capture reasoning_content already in response object
reasoning = response.choices[0].message.reasoning_content
if reasoning:
    telegram_notify(f"🧠 Agent-Y thinking...\n{reasoning[:600]}")

# What user sees in Telegram:
# 🧠 Agent-Y thinking...
# "Brief says PostgreSQL + Telegram bot. Seen this 6 times. Consistent failure:
#  async DB inside sync Telegram handlers. Using sync SQLAlchemy for Iter 1.
#  Rate limiting was bottleneck last time — adding RateLimiter task proactively."
# 📋 Plan ready. 7 tasks. Sending for review...
```

User watches the system think. Not a black box that returns results.

---

## v4.3 — TDD-ReAct (the real architectural shift — after 10 real projects)

DO NOT BUILD UNTIL: 10 real projects completed with v4.2 loop. Need real failure data.

**The inversion — codebase drives the plan, not the other way around:**

```
Current:  Plan task → Write code → Write test → Run test → pass/fail
v4.3:     Agent-Y writes pytest stub FIRST → Agent-X enters while tests_fail: loop
```

Agent-Y gains one new output field:
```python
class Task(BaseModel):
    ...
    test_skeleton: str  # actual pytest file with real assertions, not YAML criteria
    # e.g.:
    # def test_create_user_returns_token():
    #     response = client.post("/auth", json={"email": "a@b.com", "password": "x"})
    #     assert response.status_code == 200
    #     assert "access_token" in response.json()
```

Agent-X role changes from "write code + test" to "make this test pass":
```
Agent-X tools: search_codebase(), read_file(), edit_file(), run_test()
Agent-X loop:  while tests_fail → read failing assertion → search repo → edit → retry
```

Result: no more rigid DAG. Test is the spec. Placeholder detection becomes trivial.
Retry prompt always grounded in specific assertion failure, not vague error.

Gate: 10 real projects with v4.2. Watch what fails. Design tools from real data.

---

## THE FULL UPGRADED ARCHITECTURE SHAPE

```
Brief drops
    ↓
Historical Mandates built (zero LLM — memory.jsonl + Thompson)
    ↓
Agent-Y reads mandates + brief
  → streams <think> reasoning to Telegram
  → spec conflict check
  → plan emitted (3-5 task horizon only, not full 12-task upfront)
    ↓
Plan Checkpoint → user approves (Telegram, 10min timer)
    ↓
T0 Scaffold — all stubs, all __init__.py, all dirs (no LLM)
    ↓
BUILD LOOP (per task):
  [Telegram interrupt check]
  [pip install if requirements.txt]
  [inject global_interfaces + skill_vault + Historical Mandates into prompt]
  [Agent-X writes code]
  [placeholder check]
  [pytest -x --ff on task's test file]
  [retry loop max 3 — each prompt differs, rejection reason injected]
  [StateDiffSummary emitted]               ← v4.2
  [materiality gate]                       ← v4.2
    threshold hit → Agent-Y.assess()
      → surgical patch to future tasks only
      → Telegram: "Discovered X, adjusted tasks Y and Z"
    no threshold → continue, zero LLM call
  [global_interfaces updated]
  [context.md discoveries section updated]
  [Thompson Sampler updated]
    ↓
Iteration Audit (6 checks, parallel with ThreadPoolExecutor)
  1. Stub check    2. Import health    3. TODO count
  4. Runnable      5. Scope drift      6. Plan vs built
    ↓
Telegram: "Iter 1: 5/6 solid. auth.py still stub. App starts. Next iter?"
    ↓
User: [next iter] [fix first] [ship it]
    ↓
(v4.3 — after 10 real projects)
  Agent-Y writes test skeletons per task
  Agent-X: while tests_fail: → search → edit → retry
  Codebase drives the plan
```

---

## ARCHITECTURAL DECISIONS (updated 2026-03-29)

| Decision | What | Status |
|----------|------|--------|
| Sequential build | One project at a time | KEEP — state.json race still real |
| BM25 primary + embeddings hybrid | all-MiniLM-L6-v2 (90MB) | UNLOCKED — 4GB RAM |
| DeepSeek-chat | Code generation | KEEP — OpenAI-compatible swap |
| 50/15 line limits | write_file=50, file_edit=15 | KEEP — forces decomposition |
| uv always | Dependency management | KEEP — global cache |
| Shadow branches | agent-x/fix-<run_id> | KEEP — main is sacred |
| No local LLMs | Qwen/Phi-3 | KEEP — 2.2GB inference risk on 4GB |
| StateDiffSummary | Post-task signal | v4.2 — build after gaps closed |
| Historical Mandates | Memory Brief in Agent-Y prompt | v4.2 — build after gaps closed |
| TDD-ReAct | Agent-Y writes tests first | v4.3 — gate: 10 real projects |

---

## HARD RULES (no exceptions)

1. confidence < 0.85 → observer mode, pipeline stops
2. patch > 15 lines → sanitiser rejects, retry with different prompt
3. max 3 retries — each retry prompt MUST differ (rejection reason injected)
4. ALWAYS write to memory.jsonl regardless of outcome (finally: block)
5. resolve_safe_path() on EVERY file write — no exceptions
6. Orchestrator atomic write: state_tmp.json → rename (never direct json.dump)
7. Agent-Y called ONLY when: plan empty OR failed_task_streak == 2 OR materiality gate fires
8. No secrets in code — os.environ inside functions only, never module level
9. No cross-imports between phase1/ phase2/ phase3/
10. Claude NEVER commits, NEVER pushes — user commits manually

---

## PRIORITY ORDER (what to build next)

```
── PENDING GAPS (close these first) ──────────────────────────────────────
1. FIX-3b  template scaffold library                                     ← NEXT
2. FIX-19  STATE_PATH multi-project isolation
3. FIX-3c  tiered complexity gates (gate: after FIX-3b)

── FROM CLAUDE CODE LEAKED SOURCE (add after gaps closed) ────────────────
4. FIX-20  memoized context blocks        (~8L, orchestrator.py — zero risk)
5. FIX-21  large error → disk offload     (~10L, needs MEMORY_ROOT from FIX-19)
6. FIX-22  retry context compaction       (~12L, after FIX-2 retry loop clean)
7. FIX-23  plan verification gate         (~20L, after FIX-11 Telegram notify)
8. FIX-24  auto memory extraction         (~35L, after FIX-23 post-build hook)
9. FIX-25  cron scheduling in brief.yaml  (~33L, after FIX-19 MEMORY_ROOT)

── v4.2 PROACTIVE ARCHITECTURE ───────────────────────────────────────────
10. v4.2   StateDiffSummary + materiality gate     (~30 lines)
11. v4.2   Historical Mandates in Agent-Y prompt   (~30 lines — feeds from FIX-24 auto_memory.jsonl)
12. v4.2   Stream <think> reasoning to Telegram    (~10 lines)
13. Hybrid embeddings all-MiniLM-L6-v2             (after #10-12 proven)
14. v4.3   TDD-ReAct                               (gate: 10 real projects)
```

Source specs for FIX-20 through FIX-25: @docs/prompts/v41_creation_fixes.md → last section
Origin: claude-code-main/ (cloned 2026-03-31) — leaked Claude Code TypeScript source

---

## METRICS (know these cold)

- ZSPR (Zero-Shot Pass Rate): 97.1% synthetic — real baseline TBD after 10 real projects
- MATG (Mean Attempts to Green): ~1.02 on synthetic — real baseline TBD
- 276/345 entries trivial (<3 lines) — real training-ready entries: ~46
- LoRA gate: 50 real-project entries WITH <think> blocks (NOT 500 synthetic)
- Thompson decay: γ=0.95 per project completion, floor max(α,1.0)
- EB prior gate: 20+ arms AND 10+ real projects before Empirical Bayes prior trusted

---

## VIVA / PITCH QUESTIONS — KNOW THESE COLD

**"You built a cache, not a learner."**
ZSPR trajectory is the proof. 97.1% is on 5 synthetic fixtures. A cache has flat ZSPR
across project types. A learning system stays high on never-seen patterns via Skill Vault
generalization. Real proof: ZSPR on 10 diverse real projects — that measurement is next.

**"Your 97.1% is too good to be true."**
It is. 276/345 entries are trivial patches from the same 5 repos. I know this.
46 real training-ready entries. LoRA gate revised to 50 real-project entries + <think> blocks.

**"Why BM25? Embeddings are better."**
Was: 2GB VPS, sentence-transformers = 800MB OOM. Now: 4GB RAM, all-MiniLM-L6-v2 = 90MB.
Hybrid BM25 + embeddings is the next retrieval upgrade. BM25 stays for lexical bug signatures.
Embeddings add semantic matching. Fuse scores. Strictly better than either alone.

**"Why sequential? Real agent systems parallelize."**
State.json race conditions — parallel writes corrupt project state. Two build lanes max:
Lane A = active build, Lane B = background (embedding indexing, AST summarization).
Sequential codegen is not a limitation — it's the only design that doesn't corrupt state.

**"It's still waterfall even with replanning."**
Correct — today. v4.2 fixes this. StateDiffSummary after every task. Materiality gate.
Agent-Y re-assesses on discovery, not on failure. Information flows both directions.
v4.3 inverts it entirely: test-first, codebase drives the plan.

**"DeepSeek will be deprecated. Your system dies."**
OpenAI-compatible API. Change base_url + model name. Pipeline unchanged.
Fine-tuned local model (v4.0) is the exit from API dependency entirely.

**"What's your moat?"**
memory.jsonl. 605 execution traces, growing every run. Training data nobody else has.
Runs locally after fine-tuning. Zero API cost. Cannot be bought — has to be earned.

---

## WHAT NOT TO DO (Claude-specific rules)

- Do NOT re-audit old creation steps from scratch — trust this doc
- Do NOT suggest raising 50/15 line limits — architectural gate, locked
- Do NOT suggest Obsidian integration — parked at v4.2
- Do NOT commit or push — user commits manually after review
- Do NOT start next fix until all tests pass for current fix
- Do NOT re-list FIX-2 through FIX-9 as pending — they are all done, verified in code
- Do NOT build v4.3 TDD-ReAct before 10 real projects are done
- Do NOT install local LLMs — OOM risk on 4GB

---

## KEY FILES (where things live)

```
docs/BRIEFING.md                      ← YOU ARE HERE — read first every session
docs/progress.md                      ← test counts + build history
docs/session_prompts.md               ← active step queue
docs/AGENT_BEHAVIOR.md                ← full behavioral contract end-to-end
docs/prompts/v41_creation_fixes.md    ← full spec for FIX-2 through FIX-9 + FIX-3b
docs/gemini_reviews.md                ← Gemini stress-tests + VIVA PREP
docs/sonnet arch.md                   ← Perplexity architectural review (2026-03-29)
docs/chatgpt arch.md                  ← ChatGPT architectural review (2026-03-29)
CLAUDE.md                             ← hard rules + pipeline spec + upgrade queue
NEXT_SESSION.md                       ← fast path: exact next step + branch
```

---

## SESSION START PROTOCOL

1. Read this file (BRIEFING.md) — done
2. Read NEXT_SESSION.md — find exact next step
3. Ask user: "Ready to start FIX-N?" — wait for confirmation
4. Read the relevant FIX section in docs/prompts/v41_creation_fixes.md
5. Execute — run pytest after every file touched
6. Update docs/progress.md when done
7. Stop — do not proceed without user confirmation
