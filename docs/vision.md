# Agent-X + Agent-Y | Vision
# Written: 2026-03-20 — CH Y SAI SIDDHARDHA
# Updated: 2026-03-20 — ChatGPT protocol constraints integrated
# This is the north star. Every build decision points here.

---

## The Vision

User says: "I want to build a crypto bot"

```
Agent-Y (Brain) — stateless planner, no hidden memory
├── reads shared state (single source of truth)
├── thinks in steps (CoT via deepseek-reasoner)
├── designs architecture + ASCII diagram
├── outputs Plan: ordered Tasks with acceptance criteria
└── decides: PLAN | NEXT_TASK | REPLAN
         ↓
    Orchestrator (no intelligence — just enforces the loop)
    ├── loads state
    ├── calls Agent-Y → gets next task
    ├── calls Agent-X → gets result
    ├── updates state
    └── loops until done
         ↓
Agent-X (Hands) — no thinking, only execution
├── receives one Task at a time
├── generates code / patch
├── runs tests (acceptance criteria)
├── fixes its own errors (existing repair loop)
└── returns: done | failed | artifacts
         ↓
Orchestrator updates state → Agent-Y reads → decides next step or REPLAN
         ↓
Working repo. No human wrote a line of code.
```

---

## Why CI/CD Repair First

Not the destination — the proving ground.

Before building the planning loop, we need to prove:
- Agent-X can reliably fix real code (not synthetic)
- Agent-Y's reasoning produces strategies that actually work
- Memory + Thompson Sampling learns what approaches win
- The system doesn't regress when touching real repos

20+ real accepted fixes = proof. Then we build the loop.

---

## The Protocol (locked — from ChatGPT validation)

> Don't build "agents that talk". Build a controlled execution loop with strict contracts.

### Shared State — single source of truth
```json
{
  "project_id": "crypto_bot_v1",
  "goal": "Build minimal crypto trading bot",
  "plan": [
    {
      "task_id": "T1",
      "description": "Create project structure",
      "status": "done | pending | failed",
      "output": null
    }
  ],
  "current_task_id": "T2",
  "artifacts": { "files": [], "logs": [] },
  "history": []
}
```

### Agent-Y Output Schema (planner — never writes code)
```json
{
  "action": "PLAN | NEXT_TASK | REPLAN",
  "tasks": [
    {
      "task_id": "T2",
      "description": "Implement Binance API client",
      "acceptance_criteria": ["connects to testnet", "fetches price"]
    }
  ],
  "reasoning": "Why this step now",
  "next_task_id": "T2"
}
```

### Agent-X Output Schema (executor — no thinking)
```json
{
  "task_id": "T2",
  "status": "done | failed",
  "summary": "What was implemented",
  "artifacts": ["binance_client.py"],
  "errors": null
}
```

### Agent-Y Task Schema (updated — Atomic Change Set, locked 2026-03-22)
```json
{
  "task_id": "T2",
  "description": "Fix missing interface implementation",
  "files_to_change": ["auth.py", "auth_impl.py", "test_auth.py"],
  "patch_order": ["auth.py", "auth_impl.py", "test_auth.py"],
  "max_total_lines": 50,
  "acceptance_criteria": ["test_auth_validates_token passes"],
  "depends_on": ["T1"],
  "status": "pending"
}
```
Caps: 1-5 files, 15 lines per file patch, 50 lines total.
Rollback: git reset --hard HEAD (all files) — never partial.
See docs/architecture_decisions.md D11 for full design.
```

### The Orchestrator Loop
```python
while not is_done(state):
    state = load_state()
    y_output = agent_y(state)           # plan or next task
    if y_output["action"] == "PLAN":
        update_plan(state, y_output)
    task = get_current_task(state)
    x_output = agent_x(task)            # execute one task
    update_state(state, x_output)       # write result back
    # Agent-Y will read updated state next iteration
```

---

## Critical Design Rules (locked)

1. **Agent-Y is stateless** — reads shared state only, no hidden memory → prevents drift
2. **One task at a time** — no batching → debugging stays possible
3. **Every task has acceptance criteria** — Agent-X will lie without a test to pass
4. **REPLAN on 2 consecutive failures** — mandatory, not optional
5. **Orchestrator has zero intelligence** — it enforces the loop, nothing more
6. **CoT only in Agent-Y** — not Agent-X. Reasoning is expensive + slow + noisy
7. **Shared state = single source of truth** — replaces loose memory.jsonl for projects

## Task Lifecycle States (locked)
```
pending → in_progress → done
                      → failed → [increment failure counter]
                      → blocked → [dependency failed, cannot proceed]
```
`in_progress` prevents duplicate execution.
`blocked` prevents cascading failures when a dependency fails.
Never skip states — Orchestrator enforces transitions.

## Failure Type Classification (locked)
Agent-Y replans differently per failure type:
```
compile_error     → syntax or dependency issue → fix import/requirements
test_failure      → logic bug → rethink implementation strategy
patch_apply_error → diff format issue → fix patch generation prompt
runtime_error     → execution crash → add defensive code or narrow scope
```
Without this, REPLAN is blind → system thrashes.

## Task Granularity Rule (locked — hard limit)
Every task must satisfy ALL three:
- ≤ 1 file changed OR ≤ 150 lines total change
- ≤ 1 responsibility (single purpose)
- Testable in isolation (acceptance criteria = runnable test)

Bad task ❌ → "Build Binance trading system"
Good task ✅ → "Create binance_client.py with price fetch function"

If Agent-Y generates a task violating this → Orchestrator rejects it, asks Agent-Y to split.

## Hybrid Planning (locked — not full upfront)
Agent-Y does NOT fully plan everything upfront. Full plans go stale after 2-3 steps.

```
Initial call  → PLAN action    → high-level tasks (skeleton only)
Each step     → NEXT_TASK      → refined dynamically based on current state
On 2 failures → REPLAN action  → restructures remaining tasks
```

Early mistakes don't cascade. Plan adapts to what Agent-X actually built.

## Orchestrator Loop (final version)
```python
while True:
    state = load_state()
    if no_plan_exists(state):
        y_output = agent_y_plan(state)      # high-level skeleton
        save_plan(state, y_output)
    task = get_next_pending_task(state)
    mark_in_progress(task)                  # prevent duplicate execution
    x_output = agent_x_execute(task)
    update_state(state, x_output)
    if is_failure(x_output):
        increment_failure_counter(state)
    if failure_counter >= 2:
        y_output = agent_y_replan(state)    # not blind — knows failure_type
        apply_replan(state, y_output)
    if is_done(state):
        break
```

---

## What Agent-Y Becomes (v3.0+)

Right now: one error → one strategy → one patch

Target: stateless planner reading shared state, outputting Plans with Tasks.
Each Task has: description, acceptance_criteria, depends_on, prompt for Agent-X.

---

## What Agent-X Becomes (v3.0+)

Right now: fixes diffs on existing files

Target: generates new files, scaffolds projects, wires modules, runs tests at every step.
Same repair loop. Bigger inputs.

---

## The Local Model Play (v4.0)

Train Qwen2.5-7B or Phi-3 on:
- `~/.claude/CLAUDE.md` — thinking style + constraints
- `docs/session_prompts.md` — few-shot execution examples
- `memory/memory.jsonl` — what worked (training signal)
- `agent_y/CLAUDE.md` — Agent-Y hard rules

Result: model reasons exactly like this architecture. Offline. No API cost.
Outputs Plans and Tasks in exact format Agent-X expects.
That model = your moat. Nobody else has it.

---

## Executor Interface (define before v3.1, not after)

Before adding Docker/VPS backends, define this interface:
```python
class BaseExecutor:
    def apply_patch(self, repo_path: Path, patch: str) -> Result: ...
    def run_tests(self, repo_path: Path) -> Result: ...

# Implementations:
LocalExecutor   → subprocess git apply (EXISTS NOW)
DockerExecutor  → Docker SDK exec into container (v3.1)
VPSExecutor     → paramiko SSH (v3.1)
```
If not abstracted first → pipeline rewrite required when adding Docker.
Docker rule: always run with `--rm` — side effects must not persist.

## Error Type Taxonomy (expanded — locked)
```
compile_error       → syntax or import issue
test_failure        → logic bug — rethink implementation
patch_apply_error   → diff format issue
runtime_error       → execution crash
dependency_error    → missing package or version conflict (Docker/VPS)
environment_error   → missing env var, wrong Python version (Docker/VPS)
service_crash       → process died unexpectedly (Docker/VPS)
timeout_error       → execution took too long (Docker/VPS)
```

## Interface Layer (v3.2 target)

```
User (phone / laptop / CLI / local terminal)
        ↓
Interface Layer
├── Telegram bot      ← fastest win, works on phone
├── CLI tool          ← agentx fix / agentx build "idea" / agentx status
├── Local log watcher ← watchdog monitors app.log → triggers pipeline offline
└── Web UI            ← input box + status panel + logs (Streamlit or plain HTML)
        ↓
Control API (FastAPI)
├── POST /task        {"goal": "fix failing CI"}
├── POST /fix-local   {"log": "...", "repo_path": "./my-project"}
├── GET /status/{task_id}
└── GET /logs/{task_id}
        ↓
Orchestrator (Y ↔ X loop)
        ↓
Executor (local → Docker → VPS)
```

Interaction is stateless per request — state lives in backend.
Phone can disconnect. Task continues. Check status later.

## Local Dev Support (v3.2 — same pipeline, different trigger)

Solo devs without GitHub CI can still use Agent-X:

```
Trigger 1 — Webhook (current):
  GitHub CI fails → webhook → Agent-X → auto-PR

Trigger 2 — Local log watcher (v3.2):
  app.log error detected → same pipeline → git apply locally → tests run locally
  No webhook needed. Works fully offline.

Trigger 3 — CLI (v3.2):
  agentx fix --log app.log --repo ./my-project
  Dev pipes a log → pipeline runs → patch suggested → one command to apply

Trigger 4 — Telegram (v3.2):
  Send error log to bot → get fix on phone → approve → applied
```

All 4 triggers feed the same pipeline. Core doesn't change.
The only difference is the entry point and where git apply runs.

Interruptible loop (v4.x):
`/pause` `/approve` `/abort` `/change_strategy` — human controls live loop.

## Interpreter Layer (builds across v2.2 → v3.0)

Four interpreters ranked by value to the vision:

```
#3 — Patch Interpreter (D1 — CRITICAL for auto-PR)
     Before applying: plain-English explanation of what the patch does and why
     "Adds setuptools to requirements.txt — pip failed importing pkg_resources"
     → Human reads PR and understands what they're approving
     → Without this, auto-PR is a black box nobody trusts

#2 — Log Interpreter (D0 — HIGH value)
     After classification: plain-English root cause explanation
     Instead of: "DependencyError, confidence 0.99"
     Output: "pip failed at line 47 — setuptools missing due to build isolation"
     → Agent-Y gets richer context → better strategy → better patch

#4 — Result Interpreter (v3.0 — MEDIUM value)
     After fix: explains why the patch worked, what memory entries matched,
     what Thompson arm was chosen and why
     → Human understands autonomous decisions
     → Feeds post-merge awareness (L6 in risks_and_flaws.md)

#1 — Code Interpreter (v3.3 — LOW priority now)
     Run arbitrary code in sandbox
     LOCKED until Docker executor — security risk without sandboxing
```

Build order: Patch (#3) at D1 → Log (#2) at D0 → Result (#4) at v3.0 → Code (#1) at v3.3

---

## Roadmap to Vision

```
v2.1  → Real webhook repair        (DONE — 101+ accepted)
v2.2  → Context tools + auto-PR    (NEXT)
         D0: file tree + GitHub file fetch + log interpreter (#2)
         D1: auto-PR + patch interpreter (#3)
v2.3  → Multi-repo support
─────────────────────────────────────────────────────────────────
v3.0  → Orchestrator + shared state + Plan/Task loop
         Step C0: state_manager.py + task_schema.py (lifecycle states)
         Step C1: orchestrator.py (dumb loop, no intelligence)
         Step C2: Agent-Y planner output (PLAN/NEXT_TASK/REPLAN schema)
         Step C3: wire Agent-X into task execution
         Step C4: failure classification + REPLAN trigger
         + Result interpreter (#4)
         GATE: loop runs 10 iterations without collapse before C5
v3.1  → Project memory + design intelligence
         + Executor interface abstraction (LocalExecutor/DockerExecutor/VPSExecutor)
v3.2  → Interface layer: Control API + Telegram bot + CLI tool + local log watcher
v3.3  → DockerExecutor + VPSExecutor backends + Code interpreter (#1)
v4.0  → Fine-tune local model on memory.jsonl (LoRA, gate: 50 real entries + <think>)
v4.1  → Idea in → backend repo out (interruptible, phone-controllable)
v4.2  → Agent-U (UI) + Agent-D (DB/auth/storage) → full-stack repo out
v4.3  → Niche template libraries for U + D (crypto/stocks/polymarket/web)
v5.0  → Component library (earned) + local model zero API cost
```

## Multi-Agent Architecture (v4.2+)

Same Orchestrator loop, specialized agents per domain.
Each agent owns one layer. No overlap. Clean contracts through SharedState.

```
brief.yaml
    ↓
Agent-Y   → brain — plans ALL layers, splits tasks by agent type
    ↓
Orchestrator — routes tasks to correct agent, one at a time
    ↓              ↓                ↓
Agent-D        Agent-X          Agent-U
data layer     business logic   UI layer
runs first     runs second      runs third
    ↓              ↓                ↓
SharedState.global_interfaces — contract between all agents
```

---

### Agent-U (v4.2) — UI Designer

Owns: frontend templates, pages, styles, layout.
Truth signal: human approval (not pytest — UI is subjective).

HONEST SCOPE (locked — no hope-driven engineering):
```
IN SCOPE (DeepSeek proven capable):
  HTML + CSS + Jinja2 templates     → Python-rendered, no build tools
  Streamlit dashboards              → pure Python, already in our stack
  Basic vanilla JS (no framework)   → fetch + DOM, DeepSeek handles well

OUT OF SCOPE until proven (do not assume):
  React / Next.js                   → unknown DeepSeek reliability
  Angular / Vue                     → unknown DeepSeek reliability
  MERN stack                        → 4 ecosystems, too many failure points
  TypeScript strict mode            → DeepSeek makes type errors frequently
```

Gate to expand scope: prove DeepSeek success rate > 85% on 10 real React tasks.
Until then: Jinja2 + Streamlit covers most real project UIs without risk.

Human-in-the-loop (mandatory for all UI regardless of tech):
```
Agent-Y plans UI task
→ Agent-U generates component
→ Playwright screenshots it → sent to Telegram
→ User: ✅ looks good  OR  ❌ change X  OR  ✏️ adjust Y
→ ONLY after approval → next component
→ accepted → memory.jsonl → Thompson learns UI patterns
```

No separate router between agents — Orchestrator reads task.agent_type field.
SharedState.global_interfaces is the contract. No new infrastructure needed.

Gate: Playwright installed + Agent-X proven on 10+ real projects.

---

### Agent-D (v4.2) — Database, Storage, Auth

Owns: DB schemas, migrations, connections, auth, file storage.
Runs BEFORE Agent-X — X needs the data layer to exist before writing business logic.

Why Agent-D is a separate agent (not part of Agent-X):
  DB/auth is the most error-prone layer in any project.
  It has its own testing patterns (fixtures, rollbacks, migrations).
  It is completely separable from business logic.
  Agent-X focuses on pure logic. Agent-D handles all plumbing.
  Clear contract: Agent-D outputs models/schemas → Agent-X reads them.

```
Agent-Y plans data layer task
→ Agent-D builds:
    DB schema (SQLAlchemy models / Prisma)
    Migrations (Alembic / raw SQL)
    Auth (JWT + bcrypt / OAuth2 / sessions)
    Storage (S3 / local / CDN)
    Connection pool (DB URL, pool size, timeout)
→ Writes to SharedState.global_interfaces
→ Agent-X reads: model names, field types, auth endpoints
→ No guessing. No import errors. No schema mismatch.
```

Template library:
```
db_templates/
├── postgres/    SQLAlchemy + Alembic + connection pool
├── sqlite/      lightweight, no server, perfect for bots/CLI
├── mongodb/     motor async driver + document schemas
├── auth/
│   ├── jwt/     JWT + bcrypt + refresh tokens
│   └── oauth/   OAuth2 + providers (Google, GitHub)
└── storage/
    ├── s3/      boto3 + presigned URLs + multipart
    └── local/   file handling + serving
```

Gate: Agent-X proven on 10+ real projects first.

---

### Agent Communication (no router — already solved)

No separate router process. Orchestrator already routes via task.agent_type.
SharedState.global_interfaces is the contract between all agents.
Adding a router = one more failure point, more bugs, over-engineering.

```python
# Task schema already handles routing:
class Task(BaseModel):
    agent_type: str = "X"   # "X" | "D" | "U"
    ...

# Orchestrator dispatch (simple, already exists):
if task.agent_type == "D": agent_d.execute(task)
elif task.agent_type == "U": agent_u.execute(task)
else: agent_x.execute(task)   # default
```

### Execution Order (locked)

```
Agent-Y   plans everything → splits into D-tasks, X-tasks, U-tasks
Agent-D   data layer first → schema + auth + storage → SharedState
Agent-X   business logic   → reads D output → routes, services, tests
Agent-U   UI layer last    → reads X output → Jinja2/Streamlit pages
                           → human approves each component
```

Why this order is the only correct order:
  D before X: X needs models to import from
  X before U: U needs endpoints to call
  Human gates U: no objective truth for UI, approval is the test

---

### Full-Stack Project Output

```
brief.yaml: "Build crypto trading dashboard with portfolio tracker"
    ↓
Agent-Y: plan with D-tasks + X-tasks + U-tasks
    ↓
Agent-D: postgres + sqlalchemy models (Trade, Portfolio, Price)
         JWT auth
         S3 storage for trade history export
    ↓
Agent-X: FastAPI routes (trades CRUD, portfolio summary, price feed)
         business logic + pytest passing
    ↓
Agent-U: trading_dashboard template loaded
         candlestick chart component → user approves ✅
         portfolio panel → user approves ✅
         orderbook widget → user approves ✅
    ↓
working full-stack crypto dashboard
backend + frontend + auth + DB + tests
user approved every UI step
```

That is not a toy. That is a real product.

---

### Roadmap Update

```
v4.1   → idea in → backend repo out (current build)
v4.2   → Agent-U + Agent-D → idea in → full-stack repo out
v4.3   → niche template libraries for U + D (crypto/stocks/polymarket/web)
v5.0   → component library (earned) + fine-tuned local model
```

---

### Solo vs Team boundary

```
Solo buildable (v1 → v4.2):
  Agent-X + Agent-Y + Agent-U + Agent-D + Orchestrator
  LoRA fine-tuning
  Interface layer (Telegram + Streamlit)
  Niche template libraries

Needs a team (after v4.2):
  Agent-U at production quality     → frontend engineer
  Agent-D at enterprise scale       → DB/infra engineer
  Multi-repo at scale (100+ repos)  → DevOps
  Fine-tuning pipeline              → ML engineer
```

### The play
```
v1-v2  → prove it works           (DONE)
v3-v4  → make it autonomous       (building now)
v4.1   → backend repo out         → demo #1
v4.2   → full-stack repo out      → demo #2 → funding or team
v5.0   → local model, zero API cost → moat is complete
```
One person can get to v4.2. After that the project attracts people.
That's how every serious tool started.

---

## Why v2.1 Comes Before v3.0 (not negotiable)

ChatGPT suggested starting v3.0 infrastructure at B0. Rejected.

Reason: You cannot build a reliable orchestrator before Agent-X is proven
on real code. The orchestrator depends on Agent-X behaving predictably.
Right now Agent-X has only seen 5 synthetic cases. After v2.1 it will have
real repo failures. After v2.2 it will have 20+ accepted fixes.
That's the data the orchestrator needs to be reliable.

Build order is: prove hands work → prove repair loop works on real code
→ then build the brain that directs the hands.
Skipping this = building on unproven foundation.

---

## Agent-XYZ as a Universal API (v3.2 → v4.1)

The end goal: Agent-XYZ exposed as an API that any platform can call.
Not just a CLI tool or a Telegram bot — a programmable engine.

```
Any platform (Open WebUI, Cursor, OpenClaw, custom UI, CI/CD, VS Code)
        ↓ HTTP POST
FastAPI Control API          ← thin wrapper, zero logic
        ↓
Orchestrator                 ← unchanged
        ↓
Agent-Y + Agent-X            ← unchanged
```

### What the API exposes:
```
POST /project/new            {"goal": "build a quant bot"}
POST /project/fix            {"log": "...", "repo": "..."}
GET  /project/{slug}         → status, current task, progress %
GET  /projects               → all projects + status
DELETE /project/{slug}       → wipe from VPS (archive GitHub)
POST /project/{slug}/resume  → continue stalled project
```

### Platform compatibility (no extra work):
```
Open WebUI   → OpenAI-compatible wrapper (format responses like OpenAI chat)
Cursor       → MCP server — expose Agent-XYZ as a native tool
OpenClaw     → direct HTTP calls (trivial)
VS Code ext  → HTTP calls to Control API
Telegram     → already planned v3.2
Any CI/CD    → webhook → API → fix (already works today)
```

### Why this is reachable solo:
- FastAPI webhook server already exists (v2.1)
- Control API = expand the existing server, not rebuild
- Orchestrator loop doesn't change — just exposed over HTTP
- OpenAI wrapper = format shim only (~30 lines)
- MCP server = medium effort but unlocks Cursor natively

### Build order (locked):
```
v3.2  → Control API + Telegram (foundation)
v4.0  → OpenAI-compatible wrapper → Open WebUI works instantly
v4.1  → MCP server → Cursor/VS Code native integration
```

---

## The One Rule

Every build decision must answer:
"Does this move us toward v4.1 or away from it?"

If away → don't build it.
If toward → build it now, data-gate it, prove it works.
