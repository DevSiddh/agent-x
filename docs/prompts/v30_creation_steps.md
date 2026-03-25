# Agent-X v3.0 | Steps Y-C0, X-C0, Y-C1
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
       hint: str = ""         # optional — Agent-Y uses ONLY for hard constraints AcceptanceCriteria
                              # cannot express (e.g. "use requests not httpx", "factory pattern required")
                              # empty 90% of the time — Orchestrator appends to static prompt if set
       depends_on: list[str] = []
       status: Literal["pending", "in_progress", "completed", "failed", "blocked"] = "pending"
       failed_attempts: int = 0
       variations_tried: int = 0  # Best-of-N: how many variants attempted before pass

   # NOTE: hint field must be included in schemas.py — it is part of the locked Task model.

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
   - Orchestrator calls inline scaffold_project() — no cookiecutter, no external templates
   - scaffold_project(project_slug, template, repo_path) creates: src/, tests/, __init__.py,
     conftest.py, pyproject.toml stubs — pure Python, zero external dependency
   - Template arg is a hint string only ("fastapi" | "cli" | "bot" | "script") — no files to maintain
   - scaffold_project() also creates .agent/context.md with initial content:
       # {project_slug} context
       Goal: {goal from SharedState}
       Template: {template}
       Architecture: TBD
       Key files: TBD
       Decisions: TBD
       Known issues: none
       Last task: T0 — scaffold ({date})
   - .agent/context.md is committed to GitHub with every code push
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
         1. Validate 50-line limit: len(content.splitlines()) <= 50
            if exceeded → return RunResult(success=False, error="write_file: exceeds 50-line limit")
         2. Create parent directories if missing: file_path.parent.mkdir(parents=True, exist_ok=True)
         3. Write content to file_path
         4. git add file_path (subprocess, cwd=repo_path)
         5. Return RunResult(success=True)
       Never raises. All errors → RunResult(success=False, error=str(e)).
       structlog: executor.write_file.ok / executor.write_file.error
       """

   DUAL-GATE LINE LIMITS (locked — D11, never mix these two gates):
   - write_file (new file creation): 50-line limit (task cap — testability gate)
   - file_edit / apply_patch (existing file): 15-line limit (patch cap — LLM quality gate)
   Rationale: new file needs no context mapping, 50 lines is safe. Editing existing file
   risks LLM losing its place beyond 15 lines.

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
         6. update_context_md(repo_path, task) — append completed task to .agent/context.md
            Format appended: "Last task: {task_id} — {description} ({date})"
            Also update "Key files:" section with any new files_to_touch
         7. git commit + push to GitHub — code + .agent/context.md committed together
            Branch: agent-xyz/{project_slug} (never main)
         8. Return updated state

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
                 # CONTENT GENERATION ("Test is the Prompt" paradigm):
                 # Orchestrator uses a static system prompt — never constructs it dynamically.
                 # Agent-Y does NOT write code — it only provides AcceptanceCriteria + optional hint.
                 # Orchestrator builds the DeepSeek call:
                 #   system = AGENT_X_STATIC_PROMPT  (hardcoded constant — never changes)
                 #   user   = f"Task: {task.description}\n"
                 #            f"File: {file_path}\n"
                 #            f"Acceptance criteria: {task.acceptance_criteria.model_dump_json()}\n"
                 #            + (f"Constraint: {task.hint}\n" if task.hint else "")
                 # Agent-X infers entire implementation from AcceptanceCriteria I/O cases.
                 # AGENT_X_STATIC_PROMPT constant (locked — do not change per task):
                 #   "You are Agent-X. Satisfy the Acceptance Criteria exactly.
                 #    Write tests/test_<name>.py using pytest.mark.parametrize for the provided cases.
                 #    Then implement src/<name>.py to make them pass.
                 #    Hard limits: 50 lines per new file, 15 lines per edit.
                 #    Return raw Python only. No markdown. No explanation."
                 content = deepseek_call(system=AGENT_X_STATIC_PROMPT, user=user_prompt)
                 result = runner.write_file(content, file_path, repo_path)
             else:
                 result = runner.apply_patch(patch, repo_path)
             if not result.success → mark_failed, save, return

         run acceptance tests:
             # Orchestrator is dumb — pytest is truth. Agent-X wrote the parametrize test
             # file as part of the task. Orchestrator just fires pytest and trusts exit code.
             result = runner.run_tests(repo_path,
                          test_filter=task.acceptance_criteria.target_function)
             if not result.success → mark_failed(state, task.task_id, "test_failure"), save, return
             # AcceptanceCriteria cases live in schema for Agent-X to write parametrize tests.
             # Orchestrator never evaluates them directly — no dynamic eval, no custom runner.

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

---

## STEP Y-C1 — Bayesian Skill Vault + Best-of-N Sampling
# Prerequisite: Step X-C0 DONE (Orchestrator must exist).
# Adds: skill_vault.jsonl, SkillVault class, retrospective skill generation, Best-of-N execution.

```
You are building Agent-X v3.1 — Bayesian Skill Vault + Best-of-N.
Read CLAUDE.md, docs/progress.md before touching anything.
Step X-C0 must be DONE. Do not break existing tests.

CONTEXT:
Agent-Y currently injects skill context based on keyword matching only.
This step makes skills LEARN — each skill tracks Beta(α,β) and is sampled
via Thompson Sampling. Skills are auto-generated from successful replans.
Best-of-N upgrades the Orchestrator to try n=3 variations on retry, stopping
at first pass — Karpathy test-time compute on a 2GB VPS budget.

BUILD THIS STEP:

1. memory/skill_vault.jsonl — NEW FILE (empty on creation)
   Schema per entry (one JSON object per line):
   {
     "skill_id": str,           # e.g. "avoid_circular_imports_fastapi"
     "constraint_text": str,    # the generalized rule to inject
     "domain_tags": list[str],  # e.g. ["fastapi", "pydantic"]
     "embedding": list[float],  # Jina vector — reuse _get_embedding_model() from similarity.py
     "alpha": int,              # Beta dist wins (starts at 1)
     "beta": int,               # Beta dist losses (starts at 1)
     "source": str,             # "project_slug:task_id" provenance
     "created_at": str          # ISO date
   }

2. phase2/skills/__init__.py — empty package

3. phase2/skills/vault.py — NEW FILE
   Reuses: ThompsonSampler from phase2/strategy/thompson.py (arm_key = skill_id)
   Reuses: _get_embedding_model() from phase2/memory/similarity.py

   class SkillEntry(BaseModel):
       skill_id: str
       constraint_text: str
       domain_tags: list[str] = []
       embedding: list[float] = []
       alpha: int = 1
       beta: int = 1
       source: str = ""
       created_at: str = ""

   class SkillVault:
       VAULT_PATH = Path("memory/skill_vault.jsonl")
       SKILL_STATE_PATH = Path("memory/skill_state.json")
       TRUST_GATE = 7  # α+β must reach 7 before Thompson score is used

       def find_relevant(self, goal: str, k: int = 10) -> list[SkillEntry]:
           # embed goal via _get_embedding_model() (lazy, never raises)
           # cosine similarity against all skill embeddings
           # return top-k by similarity
           # if model unavailable → return all skills up to k (graceful fallback)

       def sample_top(self, skills: list[SkillEntry], n: int = 3) -> list[SkillEntry]:
           # for each skill: if α+β >= TRUST_GATE → ThompsonSampler.sample(skill_id)
           #                 else → score = 0.5 (equal probability before gate)
           # sort by score descending → return top n

       def update(self, skill_ids: list[str], won: bool) -> None:
           # ThompsonSampler.update(skill_id, won) for each
           # never raises

       def add_skill(self, entry: SkillEntry) -> None:
           # append to skill_vault.jsonl
           # init arm in ThompsonSampler with alpha=1, beta=1
           # embed if embedding is empty (lazy embed on add)
           # never raises — log error and return on failure

       def get_context_block(self, goal: str) -> str:
           # find_relevant() → sample_top() → format as:
           # "[SKILL: skill_id]\n{constraint_text}\n" for each
           # returns "" if vault is empty (never raises)

   __main__ smoke test: create vault, add_skill, find_relevant, sample_top.

4. agent_y/retrospective.py — NEW FILE
   Fires when: task.failed_attempts >= 2 AND task.status == "completed"
   (Task eventually succeeded after struggle — worth abstracting)

   def generate_skill(
       state: SharedState,
       failed_task: Task,
       failed_diffs: list[str],   # diffs from failed attempts
       winning_diff: str,          # the diff that passed
   ) -> SkillEntry | None:
       """
       Calls deepseek-reasoner with prompt:
         "Here are {n} failed diffs and 1 winning diff for task: {description}.
          Abstract the winning pivot into a generalized constraint for future tasks.
          Do NOT include specific variable names or file paths.
          Output JSON only: {skill_id, constraint_text, domain_tags}"
       Returns None if Agent-Y cannot generalize (invalid JSON or empty constraint).
       Never raises. structlog: retrospective.ok / retrospective.skip / retrospective.error
       """

5. phase3/orchestrator.py — ADD Best-of-N to run_once()

   Best-of-N rules (locked):
   - First attempt: n=1, temperature=0.4 (deterministic — save API cost)
   - On first failure: retry with n=3, temperature=0.8 (creative variants)
   - Sequential execution: apply variant 1 → test → if pass STOP
                           else rollback() → apply variant 2 → test → if pass STOP
                           else rollback() → apply variant 3 → test → if pass STOP
                           else → mark_failed
   - task.variations_tried incremented for each variant attempted
   - Skill vault updated ONCE per task outcome (not per variant)
   - rollback() = existing runner.rollback() — git checkout -- . (NOT git reset --hard)

   API call for n=3:
       response = client.chat.completions.create(
           model="deepseek-chat",
           messages=messages,
           temperature=0.8,
           n=3,
       )
       variations = [c.message.content for c in response.choices]

   Wire retrospective into post-task-success flow (after global_interfaces update):
       if task.failed_attempts >= 2 and task.status == "completed":
           skill = retrospective.generate_skill(state, task, failed_diffs, winning_diff)
           if skill:
               vault.add_skill(skill)

6. tests/test_skill_vault.py — NEW FILE
   - Test find_relevant: mock embedding model → cosine ranking works
   - Test find_relevant: model unavailable → returns all skills up to k
   - Test sample_top: skill below TRUST_GATE → score 0.5 (equal weight)
   - Test sample_top: skill above TRUST_GATE → Thompson score used
   - Test update: win → alpha+1; loss → beta+1
   - Test add_skill: persists to skill_vault.jsonl + inits Thompson arm
   - Test get_context_block: empty vault → returns ""
   - Test generate_skill: valid LLM response → SkillEntry returned
   - Test generate_skill: invalid JSON → returns None (never raises)
   - Test Best-of-N: variation 1 fails → rollback called → variation 2 tried
   - Test Best-of-N: variation 1 passes → stop (variations 2+3 not tried)
   - Test retrospective wire: failed_attempts >= 2 + completed → generate_skill called

DONE WHEN:
- pytest tests/ → all pass (zero regressions from existing suite)
- pytest tests/test_skill_vault.py → all new tests pass
- skill_vault.jsonl created (empty)
- skill_state.json created after first update()
- Best-of-N loop in orchestrator verified by tests
- Retrospective fires correctly on failed_attempts >= 2 tasks
- docs/progress.md updated: Step Y-C1 DONE
```
