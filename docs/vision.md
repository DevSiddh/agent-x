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

## Roadmap to Vision

```
v2.1  → Real webhook repair        (CURRENT — Step B0 READY)
v2.2  → Auto-PR                    (gate: 20+ real accepted fixes)
v2.3  → Multi-repo support
─────────────────────────────────────────────────────────────────
v3.0  → Orchestrator + shared state + Plan/Task loop
         Step C0: state_manager.py + task_schema.py (lifecycle states)
         Step C1: orchestrator.py (dumb loop, no intelligence)
         Step C2: Agent-Y planner output (PLAN/NEXT_TASK/REPLAN schema)
         Step C3: wire Agent-X into task execution
         Step C4: failure classification + REPLAN trigger
         GATE: loop runs 10 iterations without collapse before C5
v3.1  → Project memory + design intelligence (Agent-Y reads chatgpt_reviews.md)
         + Executor interface abstraction (LocalExecutor/DockerExecutor/VPSExecutor)
v3.2  → Interface layer: Control API + Telegram bot + CLI tool
v3.3  → DockerExecutor + VPSExecutor backends
v4.0  → Fine-tune local model on prompt stack
v4.1  → Idea in → working repo out (interruptible, phone-controllable)
```

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

## The One Rule

Every build decision must answer:
"Does this move us toward v4.1 or away from it?"

If away → don't build it.
If toward → build it now, data-gate it, prove it works.
