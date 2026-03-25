# Agent-X v3.0 | Steps Y-C0, X-C0 (PENDING — after E2)
# Creation Mode: Agent-Y plans, Agent-X builds new files (not just patches)
# Last updated: 2026-03-25
# Architecture locked: 2026-03-25 (Gemini staff engineer review)

---

## STEP Y-C0 — v3.0: Agent-Y Creation Mode
# Prerequisite: E2 DONE (or 3+ repos in memory). D1 DONE. All prior steps passing.
# Adds: "build" action, AcceptanceCriteria schema, ReplanResponse schema, SharedState schema.

```
You are building Agent-X v3.0 — Agent-Y Creation Mode.
Read CLAUDE.md, docs/progress.md before touching anything.
D1 must be DONE. Do not break existing tests.

CONTEXT:
Agent-Y currently only knows how to repair existing code.
This step adds a second mode: creation.
In creation mode, Agent-Y plans a goal into ordered Tasks.
Each Task has acceptance criteria with 3 I/O cases (anti-reward-hacking).
ReplanResponse forces root cause analysis before any new sub-tasks.

BUILD THIS STEP:

1. agent_y/schemas.py — NEW FILE
   All Pydantic v2 models for v3.0 shared state and planning.

   class AcceptanceCase(BaseModel):
       inputs: list[str]
       expected: str

   class AcceptanceCriteria(BaseModel):
       target_function: str
       cases: list[AcceptanceCase] = Field(min_length=3)
       # min 3 I/O pairs enforced by Pydantic — Happy Path + Edge Case + Error Case
       # This is the ONLY anti-reward-hacking gate — Agent-X cannot fake passing tests
       # that cover all 3 case types

   class ArtifactEntry(BaseModel):
       file: str
       last_modified_task: str
       checksum: str  # sha256 — verified before each task; halt if changed outside pipeline

   class TaskAction(str, Enum):
       SCAFFOLD   = "scaffold"
       WRITE_FILE = "write_file"
       FILE_EDIT  = "file_edit"
       RUN_TESTS  = "run_tests"

   class Task(BaseModel):
       task_id: str
       action: TaskAction
       description: str
       files_to_touch: list[str] = Field(max_length=3)
       patch_order: list[str] = []
       acceptance_criteria: AcceptanceCriteria
       depends_on: list[str] = []
       status: Literal["pending", "in_progress", "completed", "failed", "blocked"] = "pending"
       failed_attempts: int = 0

   class SharedState(BaseModel):
       project_id: str
       project_slug: str               # e.g. "crypto-bot-v1" — WORKSPACE_ROOT resolves full path
       goal: str
       plan: list[Task]
       current_task_id: str | None = None
       failed_task_streak: int = 0
       global_interfaces: dict[str, list[str]] = {}
       artifacts: list[ArtifactEntry] = []

   class ReplanAnalysis(BaseModel):
       root_cause_of_failure: str
       flaw_in_previous_approach: str
       explicit_pivot_strategy: str
       # All 3 fields required BEFORE writing new_sub_tasks
       # This hijacks DeepSeek CoT — forces structural pivot, not retry loop

   class ReplanResponse(BaseModel):
       analysis: ReplanAnalysis
       new_sub_tasks: list[Task]
       # Surgical sub-tasking ONLY: failed Task 4 → replaced with Task 4a + Task 4b
       # NEVER rewrites full plan[] — only the failed task and its immediate successors

   - Type hints on all fields. Module docstring. __main__ smoke test (instantiate each model).
   - No imports from phase1/ phase2/ phase3/ — standalone schema file.

   ## Workspace Safety (locked 2026-03-25)

   WORKSPACE_ROOT lives in .env (Config), NOT in SharedState.
   SharedState stores project_slug only (e.g. "crypto-bot-v1").
   Orchestrator resolves full path: full_path = WORKSPACE_ROOT / project_slug

   Safe path guardrail — wrap EVERY file operation:
   ```python
   def resolve_safe_path(relative: str) -> Path:
       root = Path(os.environ["WORKSPACE_ROOT"]).resolve()
       full = (root / relative).resolve()
       if not str(full).startswith(str(root)):
           raise PermissionError(f"Sandbox escape blocked: {relative}")
       return full
   ```
   All subprocess calls use cwd=resolve_safe_path(project_slug)

   T0 scaffold task:
   - First task is ALWAYS action=SCAFFOLD
   - Orchestrator runs cookiecutter with a named template
   - Templates: fastapi-template, cli-template, bot-telegram-template, script-template
   - After scaffold: tests/ folder exists before any write_file

   write_file vs file_edit:
   - write_file: new empty file creation ONLY
   - file_edit: search_block + replace_block (like git apply but safer)
   - If search_block not found in file → task FAILS immediately (no silent corruption)
   - Task 3 creates file (write_file), Task 7 modifies it (file_edit) — same Task schema

   ArtifactEntry checksum:
   - artifacts list in SharedState tracks every file written
   - Orchestrator checks sha256 checksum before each task
   - If file changed outside pipeline → HALT immediately

2. agent_y/reasoner.py — ADD creation mode

   Current actions: "repair" | "observe" | "escalate"
   Add new actions:  "plan" | "next_task" | "replan"

   New system prompt for creation mode (CREATION_SYSTEM_PROMPT constant):
       "You are a planning engine. Break a goal into ordered tasks.
        Each task must touch ≤ 3 files and have exactly 3 acceptance criteria cases:
        a Happy Path case, an Edge Case, and an Error Case.
        Output valid JSON only. Start with { and nothing else before it."

   Add method: plan_goal(goal: str, state: SharedState) -> list[Task]
       - Calls deepseek-reasoner with CREATION_SYSTEM_PROMPT
       - Returns parsed list[Task] — uses Task schema from schemas.py
       - Validates each Task: files_to_touch max 3, acceptance_criteria min 3 cases
       - On parse failure: retry once with "Your output was not valid JSON. Return only {..."
       - On second failure: raise ReasonerError("plan_goal failed after 2 attempts")
       - structlog: reasoner.plan_goal.ok / reasoner.plan_goal.error

   Add method: replan(state: SharedState, failed_task: Task,
                      failure_type: str, error_output: str,
                      failed_diff: str, thompson_note: str) -> ReplanResponse
       - Calls deepseek-reasoner with REPLAN_SYSTEM_PROMPT
       - Injects into prompt (exact order, no omissions):
           1. Failed task description
           2. failure_type (compile_error / test_failure / patch_apply_error / runtime_error)
           3. Error output — last 20 lines max
           4. files_to_touch
           5. Failed acceptance cases (which I/O pairs failed — list them explicitly)
           6. failed_diff — the actual diff/code Agent-X wrote (critical — no blind replanning)
           7. thompson_note — e.g. "compile_errors in DependencyError solved 85% by checking __init__.py"
       - Returns ReplanResponse — validates analysis has all 3 fields non-empty
       - Surgical only: new_sub_tasks replace only the failed task, never the full plan
       - structlog: reasoner.replan.ok / reasoner.replan.error

   Keep ALL existing methods (reason(), validate_strategy(), _filter_files(), _extract_json()).
   Existing repair mode UNCHANGED. No pipeline.py changes in this step.

3. tests/test_reasoner_creation.py — NEW FILE
   - Test plan_goal: mock deepseek-reasoner → valid JSON → list[Task] returned
   - Test plan_goal: Task with files_to_touch > 3 → validation error raised
   - Test plan_goal: AcceptanceCriteria with 2 cases → Pydantic min_length=3 error raised
   - Test plan_goal: bad JSON → retry → success on second attempt
   - Test plan_goal: bad JSON twice → ReasonerError raised
   - Test replan: all 7 context fields injected into prompt (check call args)
   - Test replan: missing root_cause_of_failure → ReplanResponse parse fails → ReasonerError
   - Test replan: new_sub_tasks replaces only failed task, not full plan
   - Test SharedState: failed_task_streak field updates correctly
   - Test AcceptanceCriteria: min_length=3 enforced — 2 cases raises ValidationError
   - Test Task: status transitions pending → in_progress → completed

DONE WHEN:
- pytest tests/ → all pass (zero regressions from existing suite)
- pytest tests/test_reasoner_creation.py → all new tests pass
- agent_y/schemas.py exists with all 6 Pydantic models
- agent_y/reasoner.py has plan_goal() + replan() + 3 new actions
- AcceptanceCriteria min 3 cases enforced at model level
- docs/progress.md updated: Step Y-C0 DONE — v3.0
```

---

## STEP X-C0 — v3.0: Agent-X Task Mode + Orchestrator
# Prerequisite: Step Y-C0 DONE.
# Adds: write_file() capability, Orchestrator loop, StateManager, atomic state writes.

```
You are building Agent-X v3.0 — Orchestrator + Task Executor.
Read CLAUDE.md, docs/progress.md before touching anything.
Step Y-C0 must be DONE. Do not break existing tests.

CONTEXT:
Agent-X currently only applies git diffs to existing files.
This step adds write_file() — the ability to create new files from scratch.
The Orchestrator is a dumb loop: load state → get task → Agent-X executes → update state.
Agent-Y is called ONLY when the plan is empty OR failed_task_streak == 2.

BUILD THIS STEP:

1. phase2/executor/runner.py — ADD write_file()

   def write_file(
       file_path: Path,
       content: str,
       repo_path: Path,
   ) -> RunResult:
       """
       Write new file content to disk.
       Steps:
         1. Validate 15-line limit: len(content.splitlines()) <= 15
            if exceeded → return RunResult(success=False, error="write_file: exceeds 15-line limit")
         2. Create parent directories if missing: file_path.parent.mkdir(parents=True, exist_ok=True)
         3. Write content to file_path
         4. git add file_path (subprocess, cwd=repo_path)
         5. Return RunResult(success=True)
       Never raises. All errors → RunResult(success=False, error=str(e)).
       structlog: executor.write_file.ok / executor.write_file.error
       """

   15-line limit applies to ALL writes including test files.
   pytest.mark.parametrize fits 3 I/O cases in 8-10 lines — within the limit.
   Agent-X writes the TEST FILE first (parametrize), then the implementation file.
   This is enforced by task patch_order in SharedState, not by code.

2. phase3/state_manager.py — NEW FILE

   from agent_y.schemas import SharedState, Task

   STATE_PATH = Path("memory/state.json")
   TEMP_PATH  = Path("memory/state_tmp.json")

   def load_state() -> SharedState | None:
       """Load state.json → parse as SharedState. Return None if missing."""

   def save_state(state: SharedState) -> None:
       """
       Atomic write — crash-safe, never corrupts state.json:
         1. Write to state_tmp.json (TEMP_PATH)
         2. Rename TEMP_PATH → STATE_PATH (atomic on Linux/Mac, near-atomic on Windows)
       Never direct json.dump to state.json — always via temp file + rename.
       """

   def get_next_pending_task(state: SharedState) -> Task | None:
       """Return first task where status == 'pending' and all depends_on are 'completed'.
          Returns None if no eligible task found."""

   def mark_in_progress(state: SharedState, task_id: str) -> SharedState:
       """Set task status = 'in_progress'. Returns updated state. Does NOT save — caller saves."""

   def mark_completed(state: SharedState, task_id: str) -> SharedState:
       """Set task status = 'completed', failed_task_streak = 0. Returns updated state."""

   def mark_failed(state: SharedState, task_id: str,
                   failure_type: str) -> SharedState:
       """Set task status = 'failed', increment failed_attempts + failed_task_streak."""

   def mark_blocked(state: SharedState, task_id: str) -> SharedState:
       """Set task status = 'blocked' — dependency failed, cannot proceed."""

   - All functions: type hints, structlog, never raise (errors → log + return unchanged state)
   - __main__ smoke test: create state, save, load, get_next_pending_task

3. phase3/orchestrator.py — NEW FILE

   ORCHESTRATOR LOOP (dumb — zero intelligence, enforces the loop only):

   def run_once(state: SharedState) -> SharedState:
       """
       Execute one full task cycle:

       POST-TASK SUCCESS FLOW (exact order — do not change):
         1. ast_mapper(task.files_to_touch only) — deterministic, no LLM
         2. Merge result into state.global_interfaces — overwrite per file
         3. mark_completed(state, task_id) — in memory only
         4. failed_task_streak = 0 — already done by mark_completed
         5. save_state(state) — atomic write: state_tmp.json → rename state.json
         6. Return updated state

       AGENT-Y CALL RULE (strict — no exceptions):
         Agent-Y called ONLY when:
           - state.plan is empty                     → call plan_goal() → save plan
           - state.failed_task_streak == 2           → call replan() → replace failed task
         On every other step → get_next_pending_task() → Agent-X executes → NO Agent-Y call
         This prevents runaway reasoning costs.

       TASK EXECUTION:
         task = get_next_pending_task(state)
         if task is None → log orchestrator.no_pending_tasks → return state
         mark_in_progress(task)
         save_state(state)   ← save before execution (prevents duplicate execution on crash)

         for file_path in task.patch_order:
             if is_new_file(file_path):
                 result = runner.write_file(content, file_path, repo_path)
             else:
                 result = runner.apply_patch(patch, repo_path)
             if not result.success → mark_failed, save, return

         run acceptance tests:
             for case in task.acceptance_criteria.cases:
                 result = run_parametrized_test(case, repo_path)
                 if not result.passed → mark_failed, log which case failed, return

         if all cases pass → POST-TASK SUCCESS FLOW (steps 1-6 above)
       """

   def is_done(state: SharedState) -> bool:
       """True if ALL tasks have status 'completed' or 'blocked'."""

   def run_loop(project_id: str, goal: str, repo_path: Path,
                max_iterations: int = 20) -> SharedState:
       """
       Full orchestrator loop — exits on is_done() OR max_iterations.
       Logs orchestrator.loop.start + orchestrator.loop.done at boundaries.
       Logs orchestrator.loop.max_iterations if limit hit (not an error — a safety cap).
       """

   - structlog on every state transition
   - Never raises in run_loop — all exceptions caught, logged, loop continues
   - __main__ smoke test: create mock state → run_once → assert state updated

4. tests/test_orchestrator.py — NEW FILE
   - Test run_once: successful task → global_interfaces updated from ast_mapper
   - Test run_once: atomic write — state_tmp.json renamed to state.json
   - Test run_once: all acceptance cases pass → task status = completed
   - Test run_once: one acceptance case fails → task status = failed, failure logged
   - Test run_once: failed_task_streak == 0 after success, == 2 after two failures
   - Test run_loop: Agent-Y called when plan empty (mock plan_goal)
   - Test run_loop: Agent-Y called when failed_task_streak == 2 (mock replan)
   - Test run_loop: Agent-Y NOT called on normal step-to-step progress
   - Test get_next_pending_task: blocked when depends_on task is failed
   - Test is_done: True only when ALL tasks completed or blocked
   - Test state_manager: save + load round-trip preserves all fields
   - Test write_file: creates file, git add, returns success
   - Test write_file: 16-line content → returns error, no file created

DONE WHEN:
- pytest tests/ → all pass (zero regressions from existing suite)
- pytest tests/test_orchestrator.py → all new tests pass
- phase3/orchestrator.py runs one full cycle on a mock project
- Agent-Y called ONLY when plan empty or streak==2 (verified by test)
- State written atomically — state_tmp.json → state.json (verified by test)
- global_interfaces updated after every successful task (verified by test)
- docs/progress.md updated: Step X-C0 DONE — v3.0 COMPLETE
```
