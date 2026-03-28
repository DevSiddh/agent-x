# Agent-X | Runnable Briefing
# Full audit findings + fix proposals for handoff
# Generated: 2026-03-26
# Project: Agent-X + Agent-Y — Autonomous Software Engineer
# Current state: v3 FULLY CLOSED — 569 tests, 1 failing

---

## WHAT THIS PROJECT IS

Agent-Y (brain) + Agent-X (hands) = autonomous software engineer.
User gives an idea → Agent-Y plans + designs → Agent-X builds + tests + fixes.
Loop until done. CI/CD repair was the proving ground. v3.0 = full creation mode.

Stack: Python 3.11, Pydantic v2, structlog, DeepSeek API, FastAPI, pytest.
VPS: DigitalOcean $16/mo, 2GB RAM, 1 vCPU, 70GB SSD. Sequential only. No local LLM.

Pipeline (strict order, never change):
Observer → LogParser → RegexClassifier → PreSafetyGate
→ Gateway → MemoryReuse → ThompsonSampler.sample()
→ ContextBuilder → Agent-Y Reasoner → NegativeCheck → BaselineTests
→ DeepSeekWorker → Bandit → Radon → SecurityGate
→ Executor → SyntaxReflex → ShadowTypeCheck → RegressionCheck
→ DecisionEngine → ThompsonSampler.update() → AutoPR → MemoryStore

---

## HARD RULES (never break these)

1. confidence < 0.85 → observer mode, pipeline STOPS
2. patch > 15 lines → sanitiser rejects, retry with different prompt
3. max 3 retries per failure event — each retry prompt MUST differ
4. ALWAYS append to memory/memory.jsonl regardless of outcome (use finally:)
5. shadow branch ONLY: agent-x/fix-<run_id>
6. main branch NEVER touched
7. no secrets in code — os.environ only, ALWAYS lazy (inside functions)
8. no cross-imports between phase1/ phase2/ phase3/
9. LINE LIMITS: write_file=50 lines (task cap) | file_edit=15 lines (patch cap)
10. Orchestrator atomic write: state_tmp.json → rename, never direct json.dump to state.json
11. Agent-Y called ONLY when: plan empty OR failed_task_streak == 2
12. WORKSPACE_ROOT in .env only — never hardcode paths
13. resolve_safe_path() must wrap EVERY file write — no exceptions
14. write_file for new files, file_edit for modifications — never write_file on existing files
15. AcceptanceCriteria: min 3 I/O cases (Pydantic enforced)
16. Test written FIRST (parametrize), implementation second

---

## CURRENT TEST STATE

Total: 570 collected | 569 passing | 1 FAILING
Confirmed across 3 independent runs.

---

## CRITICAL ISSUES (fix immediately — blocking)

### BUG-1: test_never_raises fails due to stale artifact on Windows
File: tests/test_project_context.py line 158
```python
# CURRENT (broken):
def test_never_raises(self):
    result = read_context(Path("/nonexistent"))
    assert result == ""

# WHY IT FAILS:
# On Windows, Path("/nonexistent") resolves to C:\nonexistent
# A previous test (line 140) called append_task(..., Path("/nonexistent"))
# which CREATED C:\nonexistent\.agent\context.md on disk.
# So read_context() finds real content instead of returning "".
```

FIX — two parts:

Part 1: Delete the stale artifact (run once):
```bash
rm -rf /c/nonexistent
```

Part 2: Fix the test so it can never recur:
```python
# tests/test_project_context.py line 158-160 — replace with:
def test_never_raises(self, tmp_path: Path) -> None:
    result = read_context(tmp_path / "does_not_exist_subdir")
    assert result == ""
```

Also fix line 138-140 (same file) — it calls append_task with /nonexistent which creates disk state:
```python
# CURRENT (line 138-140):
def test_never_raises(self, tmp_path):
    state = _make_state()
    append_task(state, _make_task("T1"), Path("/nonexistent"))

# FIX — use tmp_path so no disk pollution:
def test_never_raises(self, tmp_path: Path) -> None:
    state = _make_state()
    append_task(state, _make_task("T1"), tmp_path / "fake_repo")
```

---

## HIGH PRIORITY ISSUES (fix before v4.1)

### BUG-2: `python3` hardcoded in orchestrator — crashes on Windows
File: phase3/orchestrator.py line 213
```python
# CURRENT (broken on Windows):
["python3", "-m", "pytest", str(repo_path / "tests"), "-q",
 f"-k", target, "--tb=short"],

# FIX — sys.executable is already imported at top of file:
[sys.executable, "-m", "pytest", str(repo_path / "tests"), "-q",
 "-k", target, "--tb=short"],
```

### BUG-3: `files_to_touch` list cap is unenforced — Pydantic v2 Field(max_length=3) only applies to strings
File: agent_y/schemas.py line 47
```python
# CURRENT (wrong — max_length on Field doesn't cap list length in Pydantic v2):
files_to_touch: list[str] = Field(max_length=3)

# FIX — use max_length on the list type directly:
from typing import Annotated
files_to_touch: Annotated[list[str], Field(max_length=3)]
# OR simpler — add a model validator:
from pydantic import model_validator

@model_validator(mode="after")
def check_files_limit(self) -> "Task":
    if len(self.files_to_touch) > 3:
        raise ValueError(f"files_to_touch max 3, got {len(self.files_to_touch)}")
    return self
```

### GAP-1: `_execute_file_ops` writes placeholder content — not real code (Q4)
File: phase3/orchestrator.py lines 194-207
```python
# CURRENT — produces empty stub files:
def _execute_file_ops(task: Task, repo_path: Path) -> bool:
    for file_str in task.patch_order:
        file_path = repo_path / file_str
        if is_new_file(file_str, repo_path):
            result = write_file(file_path, f"# {file_str}\n", repo_path)  # ← PLACEHOLDER
```

This is the #1 gap between "v3 is done" and "v4.1 works". The orchestrator loop
runs correctly but produces empty files. Needs DeepSeek call here.

FIX SPEC (implement this):
```python
def _execute_file_ops(task: Task, repo_path: Path) -> bool:
    for file_str in task.patch_order:
        file_path = repo_path / file_str
        action = TaskAction.WRITE_FILE if is_new_file(file_str, repo_path) else TaskAction.FILE_EDIT

        # Build prompt for DeepSeek
        prompt = _build_agent_x_prompt(task, file_str, action)

        # Call DeepSeek
        content = _call_deepseek(prompt)
        if not content:
            return False

        # Write or edit
        if action == TaskAction.WRITE_FILE:
            result = write_file(file_path, content, repo_path)
        else:
            result = apply_patch(repo_path, content)

        if not result.success:
            log.warning("orchestrator.file_op_failed", file=file_str, error=result.error)
            return False
    return True


def _build_agent_x_prompt(task: Task, file_str: str, action: TaskAction) -> str:
    """Build full prompt for Agent-X — AGENT_X_STATIC_PROMPT + AcceptanceCriteria + hint."""
    cases_text = "\n".join(
        f"  Input: {c.inputs} → Expected: {c.expected}"
        for c in task.acceptance_criteria.cases
    )
    hint_section = f"\nHint: {task.hint}" if task.hint else ""
    action_verb = "Create" if action == TaskAction.WRITE_FILE else "Edit"
    return (
        f"{AGENT_X_STATIC_PROMPT}\n\n"
        f"Task: {action_verb} `{file_str}`\n"
        f"Description: {task.description}\n"
        f"Target function: {task.acceptance_criteria.target_function}\n"
        f"Acceptance criteria:\n{cases_text}"
        f"{hint_section}\n"
        f"File to {'create' if action == TaskAction.WRITE_FILE else 'edit'}: {file_str}"
    )


def _call_deepseek(prompt: str) -> str:
    """Call DeepSeek API. Returns raw content string or "" on failure."""
    import os
    from openai import OpenAI
    try:
        client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": AGENT_X_STATIC_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        log.error("orchestrator.deepseek_error", error=str(exc))
        return ""
```

### GAP-2: `task.hint` field exists but never injected into Agent-X prompt (Q5)
Fixed by implementing `_build_agent_x_prompt` above (hint_section line).

### GAP-3: `.agent/context.md` not committed to GitHub after each task (Q3)
File: phase3/orchestrator.py — post-task success flow (around line 155)
CLAUDE.md spec: "Code + .agent/context.md committed together after every task"

FIX — add after `append_task()` call in run_once():
```python
# After append_task(state, task, repo_path) call:
if state.github_repo:
    _commit_context(repo_path, task.task_id)

def _commit_context(repo_path: Path, task_id: str) -> None:
    """Commit .agent/context.md to GitHub after task completion."""
    import subprocess
    try:
        context_file = repo_path / ".agent" / "context.md"
        if not context_file.exists():
            return
        subprocess.run(
            ["git", "add", str(context_file)],
            cwd=repo_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"[context] update after task {task_id}"],
            cwd=repo_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "push"],
            cwd=repo_path, check=True, capture_output=True
        )
    except subprocess.CalledProcessError as exc:
        log.warning("orchestrator.context_commit_failed", task_id=task_id, error=str(exc))
```

---

## MEDIUM ISSUES (fix when encountered)

### M1: Key Files duplicated in context.md
File: phase3/project_context.py — append_task() adds files_to_touch to Key Files
on every call without dedup check.
Fix: use a set before writing:
```python
# In append_task(), when updating Key Files section:
existing_files = set(re.findall(r'`([^`]+)`', key_files_section))
new_files = [f for f in task.files_to_touch if f not in existing_files]
```

### M2: registry.jsonl status never updates
File: phase3/project_context.py — register_project() sets status="active" forever.
No "completed" or "deleted" transition exists.
Fix: add update_registry_status(slug, status) — needed for PROJECT DELETE (v3.2 spec).

### M3: post_task_comment never called on FAILURE (Q2)
File: phase3/orchestrator.py — mark_failed path is silent on PR.
Fix: in mark_failed branch, call post_task_comment with status="failed".

### M4: 4 pytest collection warnings
Files: phase2/executor/runner.py (TestRunnerDetectionError), phase2/executor/regression.py (TestReport)
Both named like test classes. pytest warns but doesn't fail.
Fix: rename to RunnerDetectionError and PatchTestReport.

### M5: context.md 80-line limit not enforced
docs.md rules say 80 lines max. append_task() keeps appending with no truncation.
No logic to cap or summarise old entries.

---

## LOW ISSUES (note only)

### L1: test_repo_cases/ has no end-to-end pipeline tests
27 test case files exist but no test runs the full pipeline through them.
These are useful for classifier accuracy testing.

### L2: RAG past fixes capped at 3 — should raise to 7 after 200+ accepted runs
Gate: 200+ accepted runs. Current: ~100. Scheduled.

### L3: BuildError always abstains (P24)
Docker logs have no Python tracebacks → classifier confidence = 0 → observer mode.
Gate: 5+ real BuildError runs. Data-gated. Do not build yet.

### L4: skill_vault.jsonl and thompson_state.json are empty
No real Orchestrator runs have happened yet. Both systems are complete code-wise
but untrained. Will self-populate when v4.1 ships and real projects run.

---

## DOCS TO UPDATE (after fixes)

1. docs/progress.md — test count: 559 → 569 (actual as of 2026-03-26)
2. docs/v30_open_questions.md — mark Q4/Q5 as IN PROGRESS when DeepSeek wiring starts

---

## V4.1 NORTH STAR — WHAT TO BUILD NEXT

v4.1 = "idea in → working repo out". The gap between now and that:

### Step 1: Wire DeepSeek into Orchestrator (GAP-1 above) — CORE
This is the only thing blocking a working autonomous loop.
Once _execute_file_ops calls DeepSeek:
- User gives goal → Agent-Y plans → Agent-X writes real code → tests run → done

### Step 2: Agent-Y plan_goal() integration
Currently Orchestrator breaks when plan is empty (logs "Agent-Y needed" and returns).
Need to call agent_y.reasoner.reason() to get initial plan when plan=[].
Files: phase3/orchestrator.py run_loop() + run_once()

### Step 3: End-to-end smoke test
Goal: "Build a function that adds two numbers"
Expected: working add.py + test_add.py committed to a test repo.
This validates the full loop works before adding complexity.

---

## FILE MAP (complete — all modules)

```
agent_y/
├── schemas.py          ← 6 Pydantic models (SharedState, Task, AcceptanceCriteria, etc.)
├── reasoner.py         ← Agent-Y: reason() → strategy + files_to_change
├── retrospective.py    ← Skill generation from successful replans

phase1/
├── webhook/server.py   ← FastAPI webhook receiver (GitHub CI events)
├── webhook/hmac_validator.py
├── log_fetcher/fetcher.py  ← GitHub API log download
├── log_fetcher/cleaner.py  ← strip ANSI + timestamps
├── dataset/schema.py

phase2/
├── pipeline.py         ← Full repair pipeline orchestration
├── classifier/regex_pass.py    ← RegexClassifier + confidence score
├── classifier/safety_gate.py   ← Pre/post safety gates
├── classifier/semantic_fallback.py  ← Embedding fallback classifier
├── patch_gen/worker.py         ← DeepSeek call + retry logic
├── patch_gen/sanitiser.py      ← Strip markdown, validate diff
├── executor/runner.py          ← git apply + multi-lang test runner
├── executor/regression.py      ← pytest before/after comparison
├── executor/security_gate.py   ← Bandit scan on patch
├── memory/store.py             ← Append-only JSONL memory
├── memory/similarity.py        ← TF-IDF + embedding hybrid RAG
├── memory/failure_classifier.py
├── context_builder.py          ← RAG context for DeepSeek
├── strategy/thompson.py        ← Thompson Sampling bandit
├── skills/vault.py             ← Bayesian Skill Vault (Beta Thompson)
├── gateway.py                  ← Rule-based gateway
├── tools/ast_mapper.py         ← File → function signatures
├── tools/blast_radius.py       ← Dependency impact analysis
├── tools/pr_creator.py         ← GitHub PR creation + task comments
├── tools/web_reader.py
├── tools/pdf_extractor.py

phase3/
├── orchestrator.py     ← Main loop: load_state → task → execute → update
├── state_manager.py    ← Task lifecycle transitions (pending/in_progress/done/failed/blocked)
├── project_context.py  ← .agent/context.md per project + registry.jsonl
├── brief_watcher.py    ← Watchdog: drop brief.yaml → triggers pipeline
├── webhook_worker.py   ← GitHub webhook → pipeline entry
├── runner.py           ← Real GitHub event runner

dashboard/
├── app.py              ← Streamlit progress dashboard
├── data.py             ← SharedState reader for dashboard

scripts/
├── telegram_bot.py     ← Telegram bot (/step /audit /approve /reject etc.)
├── verify_env.py       ← Session start health check
├── calibrate_threshold.py
├── check_memory.py

memory/
├── memory.jsonl        ← 505+ entries (all pipeline runs)
├── registry.jsonl      ← Project index (currently empty — no real runs yet)
├── skill_vault.jsonl   ← Learned skills (empty — no real runs yet)
├── thompson_state.json ← Thompson Sampling state (0 arms — no real runs yet)

fixtures/syn_001..005/  ← Real git repos for git apply tests
test_repo_cases/        ← 27 test cases for classifier accuracy
tests/                  ← 570 pytest tests
```

---

## WHAT TO TELL RUNNABLE

"This is Agent-X, an autonomous CI/CD self-healing + code generation system.
v3 is fully closed (569 tests, 1 failing due to Windows path pollution bug).

Please fix ALL issues in this file in order of priority:
1. CRITICAL: BUG-1 (test isolation — stale artifact on Windows)
2. HIGH: BUG-2 (python3 → sys.executable in orchestrator.py:213)
3. HIGH: BUG-3 (files_to_touch list cap unenforced in schemas.py)
4. HIGH: GAP-1 + GAP-2 (wire DeepSeek into _execute_file_ops + inject task.hint)
5. HIGH: GAP-3 (commit .agent/context.md to GitHub after each task)
6. MEDIUM: M1-M4 (context.md dedup, registry status, PR failure comment, pytest warnings)
7. DOCS: update progress.md test count to 569

Hard rules for ALL changes:
- Python 3.11+ with type hints on every function
- structlog JSON logging — never stdlib logging
- Pydantic v2 for all data models
- Env vars lazy inside functions — never at module level
- pathlib.Path everywhere
- Max 50 lines per new file, max 15 lines per edit
- Run pytest after every change — all tests must pass before next change
- Never commit — I commit manually after review"
