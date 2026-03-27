# Agent-XYZ | Behavioral Specification
# Author: CH Y SAI SIDDHARDHA
# Last updated: 2026-03-27
# Purpose: defines exactly how Agent-XYZ behaves end-to-end
# Read this when: starting a new session, adding a feature, or reviewing the product
# This is the source of truth for WHAT the agent does and HOW it does it

---

## THE ONE-LINE SUMMARY

User drops a brief → Agent-XYZ plans, audits, builds in layers, catches problems early,
accepts user corrections mid-build → working repo out.

---

## THE FULL LOOP (how every project runs)

```
brief.yaml dropped
        ↓
PHASE 1 — PLANNING (Agent-Y)
  Agent-Y reads brief → generates plan (tasks + architecture)
        ↓
PHASE 2 — SPEC CONFLICT CHECK (FIX-11, part 1)
  Detect contradictions in user specs BEFORE building
  If conflict found → tell user + offer 3 options + timer
  No response → use recommended option
        ↓
PHASE 3 — PLAN CHECKPOINT (FIX-11, part 2)
  Show plan to user in their language (technical or plain English)
  technical user → task list + file names
  general user   → plain English + business decisions
  Timer: 10 min (PLAN_APPROVAL_TIMEOUT in .env)
  ✅ approve     → proceed
  ✏️  change      → replan (max 3 rounds) → show again
  no response    → skip optional tasks → proceed with core
        ↓
PHASE 4 — SCAFFOLD (FIX-3)
  Create all folders + stub files + __init__.py
  All files exist as stubs before any implementation starts
  No "file not found" errors possible after this point
        ↓
PHASE 5 — BUILD LOOP (Agent-X, one task at a time)
  For each task:
    [INTERRUPT CHECK (FIX-12)] ← check Telegram before every task
      "stop"            → halt, report what was built and what wasn't
      "skip X"          → cascade skip X + all tasks that depend on X
      "X already exists"→ same as skip
      "change X to Y"   → surgical replan on remaining tasks only
      no message        → proceed
    install dependencies (FIX-2)
    inject global_interfaces into prompt (FIX-1)
    call DeepSeek → write file (50 line cap)
    check for placeholder code (FIX-9)
    run pytest
    if fail → retry (max 3, each prompt must differ)
    if 2 consecutive failures → replan with failed_diff injected (FIX-6)
    update .agent/context.md + global_interfaces
        ↓
PHASE 6 — ITERATION AUDIT (FIX-13)
  After all tasks complete, before user sees result:
    stub files still present?
    all imports resolve?
    any TODO/FIXME remaining?
    main entry point runnable?
    scope drift? (Agent-X wrote files outside files_to_touch?)
    plan vs built: tasks marked DONE vs files that actually exist?
  Report sent to Telegram:
    "Iter 1 done. 5/6 files solid. 1 stub in auth.py. App starts. Ready for Iter 2?"
  Audit report injected into next iteration's plan_goal() context
        ↓
PHASE 7 — USER DECISION
  ✅ next iteration  → back to PHASE 1 with audit context
  🔧 fix issues first → targeted replan on flagged items only
  ✅ ship it          → push to GitHub, done
```

---

## ITERATION MODEL (how complex projects are built)

No project is built in one shot. Projects are built in layers.

```
Iteration 1:  Core foundation (4-5 files, tests pass, app starts)
Iteration 2:  Features layer (3-4 more files, core + new functionality)
Iteration 3:  Polish + edge cases (error handling, validation, docs)
```

Why iterations beat one-shot:
- Compounding failure rate: 0.9^10 = 35% end-to-end success for 10 files
- Iteration model: each layer builds on proven ground → stays above 85%
- Audit gate between iterations: broken Iter 1 never infects Iter 2
- User reviews each layer: wrong direction caught early, not after 10 files

---

## SPEC CONFLICT DETECTION (detail)

Runs at Plan Checkpoint BEFORE any code is written.
One DeepSeek call. ~$0.001.

Common conflicts caught:
```
OAuth2 requested  + REST API only project  → suggest JWT instead
PostgreSQL requested + no DB config in brief → ask or default to SQLite
Email sending requested + no SMTP in brief → flag missing config
Frontend requested + no HTML/CSS in stack  → clarify scope
Async requested + VPS = 1 vCPU constraint  → reject, suggest sync
```

Output format (Telegram):
```
⚠️ Spec conflict: [what was requested] + [why it conflicts]
Options:
  A. [alternative 1] ← recommended
  B. [alternative 2]
  C. [alternative 3]
No reply in 10 min → using Option A.
```

---

## USER TYPE DETECTION (detail)

Detected from brief.yaml language at plan time. Zero API call — keyword check.

```python
TECHNICAL_KEYWORDS = [
    "FastAPI", "SQLAlchemy", "endpoint", "schema", "pytest",
    "Pydantic", "async", "middleware", "migration", "ORM"
]
user_type = "technical" if any(kw in goal for kw in TECHNICAL_KEYWORDS) else "general"
```

Technical user sees:
```
Plan: 8 tasks | 6 files
T1: models.py — User, Todo (SQLAlchemy Base)
T2: schemas.py — Pydantic request/response models
T3: routes.py — CRUD endpoints (/todos GET POST PUT DELETE)
...
[✅ Build] [✏️ Change] — 10 min timer
```

General user sees:
```
Got it! Here's what I'll build:

✅ Core (always built):
   • Todo list — add, edit, delete items
   • Save everything to a database

🔵 Optional (your choice):
   • User accounts (keeps your todos private) ← recommended
   • Email reminders ← adds complexity

No reply in 10 min → building with user accounts, skipping email.
[✅ Everything] [🔵 Core + accounts] [⚡ Core only]
```

---

## MID-TASK INTERRUPT (detail)

Checked before every single task. Zero API cost — local message parsing.

Why other agents can't do this:
- Claude Code, Codex, OpenClaw: monolithic execution, no task boundaries
- Message arrives mid-execution → queued → read only after action completes → too late
- Agent-XYZ: atomic 50-line tasks → natural interrupt window between every task

Intent detection (keyword-based, no LLM):
```
"stop" / "halt" / "cancel"         → STOP: halt loop, report status
"skip X" / "X exists" / "don't X"  → SKIP: cascade X + dependents
"change X to Y" / "instead of X"   → MODIFY: surgical replan
anything else                       → CONTINUE: proceed normally
```

SKIP cascade (TaskStatus.SKIPPED):
```
User: "skip auth"
→ find tasks with "auth" in description
→ mark them SKIPPED
→ find all tasks with depends_on containing any SKIPPED id → also SKIPPED
→ continue remaining tasks
→ report: "Skipped T4 (auth), T5 (middleware — depends on T4). Built T1-T3, T6-T8."
```

---

## ITERATION AUDIT (detail)

Runs after all tasks complete. Zero API cost — file analysis only.

Six checks:
```
1. Stub check:    grep for "# stub" / pass-only function bodies
2. Import health: attempt import of each module → catch ImportError
3. TODO count:    grep for TODO/FIXME/HACK → measure debt
4. Runnable:      from main import app (or equivalent) → no crash
5. Scope drift:   files_written vs files_to_touch in task spec
6. Plan vs built: tasks marked DONE vs files that actually exist + are non-stub
```

Audit report injected into next plan_goal() context:
```
Agent-Y knows exactly what's broken before planning next iteration.
No blind planning. No building on broken ground.
```

---

## MULTI-LANGUAGE BACKEND SUPPORT

User has the right to choose their backend language via brief.yaml.
Default is Python. All other languages are opt-in.

```yaml
# brief.yaml
goal: "build a REST API for todo management"
language: python       # python | nodejs | go | typescript (default: python)
github_token: optional # user's own GitHub token (optional)
```

Language tiers (honest DeepSeek reliability):
```
Tier 1 — use now:
  python      proven, primary stack, 657 tests passing
  nodejs      DeepSeek handles Express/Fastify + jest well

Tier 2 — usable, warn user about retry risk:
  go          clean syntax, go test simple, DeepSeek decent
  typescript  moderate reliability, type errors recoverable

Tier 3/4 — warn strongly, suggest alternative:
  rust/java/csharp/php → DeepSeek unreliable, many retries likely
```

Plan Checkpoint warning for Tier 2:
  "Go is supported but may need more retries than Python.
   Proceed with Go? [✅ Yes] [🔄 Switch to Python]"

What changes per language (executor already partially multi-language from v2.1.6):
```
python      uv pip install  + pytest      + requirements.txt
nodejs      npm install     + jest        + package.json
go          go mod tidy     + go test     + go.mod
typescript  npm install     + jest+ts-jest + tsconfig.json
```

Template library language dimension:
```
templates/web/fastapi_crud/   Python  (exists)
templates/web/express_crud/   Node.js (build when Node.js proven)
templates/web/gin_crud/       Go      (build after express_crud proven)
```

Rule: build Tier 1 templates first, prove reliability, then Tier 2.
Never build Tier 3/4 templates — guide user to better choice at Plan Checkpoint.

---

## FOUR QUALITY WALLS

```
Wall 1 — Spec Conflict (FIX-11 part 1)
  WHEN: before building starts
  CATCHES: wrong specs, missing config, incompatible requirements
  COST: 1 DeepSeek call (~$0.001)

Wall 2 — Plan Checkpoint (FIX-11 part 2)
  WHEN: before building starts
  CATCHES: wrong plan, wrong architecture, wrong scope
  COST: 1 Telegram message

Wall 3 — Mid-task Interrupt (FIX-12)
  WHEN: between every task during build
  CATCHES: user course correction, duplicate features, wrong direction
  COST: zero (local parsing)

Wall 4 — Iteration Audit (FIX-13)
  WHEN: after iteration completes, before next starts
  CATCHES: stubs, broken imports, scope drift, plan vs reality gap
  COST: zero (file analysis)
```

---

## COST PROFILE (full picture)

```
Per project:
  Agent-Y plan_goal()        1 DeepSeek call      ~$0.002
  Spec conflict check        1 DeepSeek call      ~$0.001
  Per task (Agent-X)         1 DeepSeek call      ~$0.003
  Per retry                  1 DeepSeek call      ~$0.003
  Replan (if triggered)      1 DeepSeek call      ~$0.002
  Plan Checkpoint            0 API calls          free
  Interrupt handling         0 API calls          free
  Iteration Audit            0 API calls          free

Typical 8-task project, zero retries:  ~$0.03
Typical 8-task project, some retries:  ~$0.05-0.08
```

The quality walls add ~$0.003 per project. Negligible.

---

## THREE-TIER KNOWLEDGE SYSTEM

```
Tier 1 — Templates (static, niche-organized, available now)
  Hand-curated per domain. Proven structure + correct dependencies.
  Agent-X only fills in custom logic — structure never generated from scratch.

Tier 2 — RAG patterns (dynamic, grows with every run)
  memory.jsonl → BM25 retrieves what worked for similar past projects.
  When no template matches → RAG fills the gap with proven patterns.
  "build polymarket arb bot" → retrieves similar exchange/signal patterns.

Tier 3 — Component library (v5.0, earned)
  Proven full implementations after 100 real project runs.
  Not built — earned. Emerges from memory.jsonl naturally.
```

---

## TEMPLATE SCAFFOLD LIBRARY (FIX-3b)

Organized by NICHE (domain), not just by tech stack.
Niche templates carry domain knowledge — correct dependencies, patterns, structure.
Agent-X fills in strategy/business logic only. Everything structural is pre-solved.

```
templates/
├── crypto/
│   ├── price_feed/        ccxt + websocket + pandas base
│   ├── trading_bot/       strategy + order execution + risk management
│   └── portfolio_tracker/ multi-exchange + PnL + reporting
├── stocks/
│   ├── screener/          yfinance + signals + alerts
│   └── backtester/        pandas + ta-lib + performance metrics
├── polymarket/
│   └── market_bot/        API client + odds tracker + position manager
├── web/
│   ├── fastapi_crud/      models + routes + auth
│   └── dashboard/         Streamlit + charts + live data
├── bots/
│   ├── telegram_bot/      polling + handlers + commands
│   └── discord_bot/       slash commands + embeds
├── data/
│   └── pipeline/          scraper + ETL + storage
└── manifest.yaml          all templates + niche tags + confidence threshold
```

How template matching works (zero API cost):
```
brief.yaml goal → keyword match against manifest.yaml tags
Match found (≥2 tags) → load template → fill {{placeholders}}
                       → Agent-X generates custom logic only
                       → ~40-60% fewer DeepSeek calls per project
No match            → RAG query on memory.jsonl for similar patterns
                       → inject top 3 patterns into Agent-Y prompt
                       → Plan Checkpoint shows generated plan to user
                       → user confirms or corrects
```

RAG integration point:
```
No template match → BM25 searches memory.jsonl:
  query = failure_category + goal keywords
  returns top 3 accepted patterns from similar past projects
  injected as context: "Similar past projects used these patterns..."
  Agent-Y generates informed plan (not blank canvas)
  Plan shown at checkpoint — user always confirms before build
```

Difference from v5.0 component library:
  Templates = structure + dependencies (hand-curated, now)
  RAG = proven patterns from past runs (grows automatically)
  v5.0 library = proven full implementations (earned after 100 runs)

---

## COMPONENT LIBRARY EVOLUTION (v5.0 path)

Today: generate everything from scratch (high failure rate at scale)
Future: assemble proven components (high success rate at any scale)

```
10 real projects  → patterns emerge in memory.jsonl
50 real projects  → FastAPI auth module proven (40+ accepted runs)
100 real projects → component library formed naturally
v5.0              → Agent-Y selects components, Agent-X glues (~10 lines)
```

The component library is not built — it is earned through real project runs.
Every project run is a component being proven. memory.jsonl IS the library.

---

## WHAT MAKES THIS DIFFERENT FROM OTHER AGENTS

```
Feature                  Claude Code  Codex  Agent-XYZ
──────────────────────────────────────────────────────
Plan shown before build      ❌         ❌       ✅ FIX-11
Spec conflict detection      ❌         ❌       ✅ FIX-11
User type adaptation         ❌         ❌       ✅ FIX-11
Mid-build interrupts         ❌         ❌       ✅ FIX-12
Cascade skip                 ❌         ❌       ✅ FIX-12
Iteration audit gate         ❌         ❌       ✅ FIX-13
Learns from every run        ❌         ❌       ✅ memory.jsonl
Thompson-sampled strategies  ❌         ❌       ✅ thompson_state.json
```

The architectural advantage: atomic 50-line tasks create natural interrupt/audit windows.
Other agents cannot add these features without redesign. We have them for free.

---

## PRODUCTION SETUP (3 gaps — must be resolved before real use)

---

### GAP 1 — Environment mismatch (Windows dev vs Ubuntu VPS)

Not a problem by design. Agent-XYZ runs entirely ON the VPS.
Windows is only used to view results (Telegram, browser).

```
Windows machine         VPS (Ubuntu)
────────────────        ─────────────────────────────
Telegram app      ←──→ Telegram bot (running as service)
Browser           ←──→ Streamlit dashboard (running as service)
brief.yaml write  ──→  watchdog picks it up
                        pytest, git, DeepSeek — all run here
```

One real gap: projects built by Agent-XYZ are for Linux.
If user wants to run them on Windows locally → path/line-ending issues possible.
For deployment (FastAPI, bots, CLIs) → always Linux anyway. Not a real problem.
Docker executor (v3.3) will add per-project sandboxing if needed.

---

### GAP 2 — GitHub token for multiple users

Current: one GITHUB_TOKEN in .env → all repos created in system account.

Multi-user solution (v4.1):
```
brief.yaml can include optional field:
  github_token: "ghp_xxx"   ← user's own token

Behavior:
  token in brief.yaml → repos created in user's GitHub account
  no token            → repos created in system GitHub account (default)
  user can always fork/transfer repos after build
```

Proper OAuth (v5.0): user visits Agent-XYZ URL → "Connect GitHub" → OAuth flow.
Not needed until multiple real users exist.

---

### GAP 3 — Process persistence (closing terminal kills everything)

Fixed by 3 systemd services created by vps_setup.sh:

```
agentx-telegram.service    Telegram bot — polls + responds to messages
agentx-webhook.service     FastAPI webhook server — receives GitHub events
agentx-dashboard.service   Streamlit dashboard — project status UI
```

All three:
- Start automatically on VPS boot
- Restart automatically on crash (RestartSec=10)
- Survive terminal close, SSH disconnect, everything
- Logs: journalctl -u agentx-telegram -f

Check status:
  sudo systemctl status agentx-telegram agentx-webhook agentx-dashboard

If any service fails to start → check path in ExecStart matches actual file location.

---

## BUILD ORDER (locked)

```
FIX-1 to FIX-9   creation mode works (current sprint)
FIX-10           BM25F precision at scale
FIX-11           Plan Checkpoint + Spec Conflict + User Type UX
FIX-12           Mid-task Interrupt + SKIPPED cascade
FIX-13           Iteration Audit Gate
v5.0             Component assembly model (earned, not built)
```

Do not reorder. Each fix depends on the previous working correctly.

---

## FILES INVOLVED IN LOOP CONTROL LAYER (FIX-11/12/13)

```
phase3/plan_checkpoint.py    NEW — detect_user_type, format_plan, run_checkpoint
phase3/interrupt_handler.py  NEW — parse_intent, cascade_skip, check_interrupts
phase3/iteration_audit.py    NEW — run_audit, AuditReport
phase3/orchestrator.py       MOD — plan checkpoint + interrupt check + audit call
phase3/schemas.py            MOD — TaskStatus.SKIPPED, interrupt_queue, plan_approved
phase3/telegram_bot.py       MOD — pipe messages to interrupt_queue, send audit report
agent_y/reasoner.py          MOD — interpret_plan_for_user, spec conflict detection
.env.example                 MOD — PLAN_APPROVAL_TIMEOUT=600
```

Total new code: ~170 lines across 3 new files + targeted additions to 5 existing files.
