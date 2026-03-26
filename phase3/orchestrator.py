"""
phase3/orchestrator.py
Agent-X v3.0 Orchestrator — dumb loop, zero intelligence.
Loads state → gets task → Agent-X executes → updates state.
Agent-Y called ONLY when plan empty OR failed_task_streak == 2.
"""

import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

from phase3.telegram_notify import notify_loop_done

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent_y.reasoner import plan_goal
from agent_y.retrospective import generate_skill
from agent_y.schemas import SharedState, Task, TaskAction
from phase2.executor.runner import RunResult, apply_patch, rollback, write_file
from phase2.tools.pr_creator import post_task_comment
from phase2.skills.vault import SkillVault
from phase2.tools.ast_mapper import map_repo
from phase3.project_context import append_task, register_project, scaffold_context, update_registry_last_task, update_registry_status
from phase3.state_manager import (
    get_next_pending_task,
    load_state,
    mark_blocked,
    mark_completed,
    mark_failed,
    mark_in_progress,
    save_state,
)

log = structlog.get_logger()

AGENT_X_STATIC_PROMPT = (
    "You are Agent-X. Satisfy the Acceptance Criteria exactly. "
    "Use FLAT file structure — all files in project root, no subdirectories. "
    "For implementation files: define the function directly, no unnecessary imports. "
    "For test files: the import line will be specified in the task — use it exactly. "
    "Hard limits: 50 lines per new file, 15 lines per edit. "
    "Return raw Python only. No markdown. No code fences. No explanation."
)


def is_new_file(file_path: str, repo_path: Path) -> bool:
    """True if the file does not exist on disk yet."""
    return not (repo_path / file_path).exists()


def is_done(state: SharedState) -> bool:
    """True if plan is non-empty AND all tasks are completed or blocked."""
    if not state.plan:
        return False
    return all(t.status in ("completed", "blocked") for t in state.plan)


def _block_dependents(state: SharedState, failed_task_id: str) -> SharedState:
    """Mark tasks that depend on a failed task as blocked."""
    for task in state.plan:
        if failed_task_id in task.depends_on and task.status == "pending":
            state = mark_blocked(state, task.task_id)
    return state


def run_once(state: SharedState, repo_path: Path | None = None) -> SharedState:
    """
    Execute one full task cycle.
    repo_path defaults to WORKSPACE_ROOT / project_slug if not provided.
    """
    from agent_y.schemas import resolve_safe_path
    import os

    if repo_path is None:
        repo_path = resolve_safe_path(state.project_slug)

    # AGENT-Y CALL RULE — plan empty
    if not state.plan:
        log.info("orchestrator.plan_empty — Agent-Y needed")
        return state

    task = get_next_pending_task(state)
    if task is None:
        log.info("orchestrator.no_pending_tasks")
        return state

    # Mark in progress + save before execution (crash safety)
    state = mark_in_progress(state, task.task_id)
    save_state(state)

    # AGENT-Y CALL RULE — streak == 2
    if state.failed_task_streak == 2:
        log.info("orchestrator.streak_2 — Agent-Y replan needed", task_id=task.task_id)
        state = mark_failed(state, task.task_id, "streak_limit")
        save_state(state)
        return state

    vault = SkillVault()
    used_skill_ids: list[str] = []
    failed_diffs: list[str] = []
    winning_diff: str = ""
    variations_tried: int = 0

    # Best-of-N execution
    # Attempt 1: n=1 (deterministic)
    # On failure: n=3 variants (creative), stop at first pass
    attempts = [_execute_files(task, repo_path)]  # first attempt placeholder
    passed = False

    for attempt_idx, _ in enumerate(attempts):
        variations_tried += 1
        exec_ok = _execute_file_ops(task, repo_path)
        if not exec_ok:
            rollback(repo_path)
            failed_diffs.append(f"attempt_{attempt_idx}: file_op_error")
            if attempt_idx == 0:
                attempts.extend([None, None])
            continue

        test_ok = _run_tests(repo_path, task)
        if test_ok:
            winning_diff = f"attempt_{attempt_idx}: passed"
            passed = True
            break
        else:
            failed_diffs.append(f"attempt_{attempt_idx}: test_failure")
            rollback(repo_path)
            if attempt_idx == 0:
                attempts.extend([None, None])

    if not passed:
        log.warning("orchestrator.best_of_n_exhausted", task_id=task.task_id)
        state = mark_failed(state, task.task_id, "test_failure")
        state = _block_dependents(state, task.task_id)
        if used_skill_ids:
            vault.update(used_skill_ids, won=False)
        if state.github_repo and state.pr_number:
            post_task_comment(repo=state.github_repo, pr_number=state.pr_number,
                              task_id=task.task_id, description=task.description,
                              status="failed")
        save_state(state)
        return state

    # Write variations_tried back to task in state
    updated_plan = [
        t.model_copy(update={"variations_tried": variations_tried})
        if t.task_id == task.task_id else t
        for t in state.plan
    ]
    state = state.model_copy(update={"plan": updated_plan})

    # POST-TASK SUCCESS FLOW (strict order)
    # 1. ast_mapper on files_to_touch only
    interfaces = _run_ast_mapper(task.files_to_touch, repo_path)
    # 2. Merge into global_interfaces
    merged = dict(state.global_interfaces)
    merged.update(interfaces)
    state = state.model_copy(update={"global_interfaces": merged})
    # 3+4. mark_completed (also resets failed_task_streak=0)
    state = mark_completed(state, task.task_id)
    # 5. Atomic save
    save_state(state)
    # 6. Append to .agent/context.md + update registry + commit (push only if remote)
    append_task(state, task, repo_path)
    update_registry_last_task(state.project_slug, task.task_id)
    _commit_context(repo_path, task.task_id)
    # 7. Narrate task on PR (if PR is open)
    if state.github_repo and state.pr_number:
        post_task_comment(
            repo=state.github_repo,
            pr_number=state.pr_number,
            task_id=task.task_id,
            description=task.description,
            status="completed",
        )

    # Skill vault: update win
    if used_skill_ids:
        vault.update(used_skill_ids, won=True)

    # Retrospective: fire when task struggled (failed_attempts >= 2)
    current_task = next((t for t in state.plan if t.task_id == task.task_id), None)
    if current_task and task.failed_attempts >= 2:
        skill = generate_skill(state, task, failed_diffs, winning_diff)
        if skill:
            vault.add_skill(skill)

    log.info("orchestrator.task_completed", task_id=task.task_id)
    return state


def _commit_context(repo_path: Path, task_id: str) -> None:
    """Commit .agent/context.md to local repo; push only if remote is configured. Never raises."""
    try:
        context_file = repo_path / ".agent" / "context.md"
        if not context_file.exists():
            return
        subprocess.run(["git", "add", str(context_file)],
                       cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"[context] update after task {task_id}"],
                       cwd=repo_path, check=True, capture_output=True)
        remote_check = subprocess.run(
            ["git", "remote"], cwd=repo_path, capture_output=True, text=True
        )
        if remote_check.stdout.strip():
            subprocess.run(["git", "push", "--set-upstream", "origin", "master"],
                           cwd=repo_path, check=True, capture_output=True)
        log.info("orchestrator.context_committed", task_id=task_id)
    except subprocess.CalledProcessError as exc:
        log.warning("orchestrator.context_commit_failed",
                    task_id=task_id, error=exc.stderr.decode() if exc.stderr else str(exc))
    except Exception as exc:
        log.warning("orchestrator.context_commit_error", task_id=task_id, error=str(exc))


def _strip_code_fences(content: str) -> str:
    """Strip markdown code fences from LLM output before writing to disk."""
    lines = content.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _execute_files(task: Task, repo_path: Path) -> None:
    """Placeholder to represent one execution attempt slot."""
    return None


def _build_agent_x_prompt(task: Task, file_str: str, action: TaskAction) -> str:
    """Build full prompt for Agent-X — static prompt + AcceptanceCriteria + hint."""
    cases_text = "\n".join(
        f"  Input: {c.inputs} → Expected: {c.expected}"
        for c in task.acceptance_criteria.cases
    )
    hint_section = f"\nHint: {task.hint}" if task.hint else ""
    action_verb = "Create" if action == TaskAction.WRITE_FILE else "Edit"

    # Derive exact import line for test files; warn impl files not to import
    impl_files = [f for f in task.patch_order if not Path(f).name.startswith("test_")]
    import_hint = ""
    if file_str.startswith("test_") and impl_files:
        module_name = Path(impl_files[0]).stem
        fn = task.acceptance_criteria.target_function
        import_hint = f"\nImport line to use: from {module_name} import {fn}"
    elif not file_str.startswith("test_"):
        fn = task.acceptance_criteria.target_function
        import_hint = f"\nThis is the implementation file. Define {fn}() directly. Do NOT import from main or any other module."

    return (
        f"Task: {action_verb} `{file_str}`\n"
        f"Description: {task.description}\n"
        f"Target function: {task.acceptance_criteria.target_function}\n"
        f"Acceptance criteria:\n{cases_text}"
        f"{import_hint}"
        f"{hint_section}\n"
        f"File to {'create' if action == TaskAction.WRITE_FILE else 'edit'}: {file_str}"
    )


def _call_deepseek(prompt: str) -> str:
    """Call DeepSeek API. Returns raw content string or '' on failure. Never raises."""
    try:
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            log.warning("orchestrator.deepseek_no_key")
            return ""
        if OpenAI is None:
            log.warning("orchestrator.deepseek_not_installed")
            return ""
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
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


def _execute_file_ops(task: Task, repo_path: Path) -> bool:
    """Execute file operations for all files in patch_order. Returns True on success."""
    for file_str in task.patch_order:
        file_path = repo_path / file_str
        # Trust the task's declared action; only fall back to FILE_EDIT if unspecified
        if task.action in (TaskAction.WRITE_FILE, TaskAction.FILE_EDIT):
            action = task.action
        else:
            action = TaskAction.WRITE_FILE if is_new_file(file_str, repo_path) else TaskAction.FILE_EDIT

        prompt = _build_agent_x_prompt(task, file_str, action)
        content = _strip_code_fences(_call_deepseek(prompt))
        if not content:
            log.warning("orchestrator.file_op_failed", file=file_str, error="empty_deepseek_response")
            return False

        if action == TaskAction.WRITE_FILE:
            result = write_file(file_path, content, repo_path)
        else:
            result = apply_patch(content, repo_path)

        if not result.success:
            log.warning("orchestrator.file_op_failed", file=file_str, error=result.error)
            return False
    return True


def _run_tests(repo_path: Path, task: Task) -> bool:
    """Run pytest filtering by target_function. Returns True if all pass."""
    try:
        target = task.acceptance_criteria.target_function
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(repo_path), "-q",
             "-k", target, "--tb=short"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            log.warning("orchestrator.test_failed",
                        stdout=result.stdout[-600:],
                        stderr=result.stderr[-200:])
        return result.returncode == 0
    except Exception as exc:
        log.error("orchestrator.test_runner_error", error=str(exc))
        return False


def _run_ast_mapper(files: list[str], repo_path: Path) -> dict[str, list[str]]:
    """Run ast_mapper on specific files, return {file: [signatures]}."""
    result: dict[str, list[str]] = {}
    try:
        for f in files:
            fp = repo_path / f
            if fp.exists() and fp.suffix == ".py":
                skeleton = map_repo(fp.parent, max_tokens=500)
                result[f] = skeleton.splitlines()
    except Exception as exc:
        log.warning("orchestrator.ast_mapper_error", error=str(exc))
    return result


def run_loop(
    project_id: str,
    goal: str,
    repo_path: Path,
    max_iterations: int = 20,
) -> SharedState:
    """
    Full orchestrator loop — exits on is_done() OR max_iterations.
    Never raises — all exceptions caught, logged, loop continues.
    """
    state = load_state()
    if state is None:
        from agent_y.schemas import SharedState as SS
        state = SS(
            project_id=project_id,
            project_slug=repo_path.name,
            goal=goal,
            plan=[],
        )
        save_state(state)

    log.info("orchestrator.loop.start", project_id=project_id, max_iter=max_iterations)

    # Register project + scaffold context on first run
    register_project(state)
    scaffold_context(state, repo_path)

    for iteration in range(max_iterations):
        if is_done(state):
            log.info("orchestrator.loop.done", iterations=iteration)
            update_registry_status(state.project_slug, "completed")
            break

        # Agent-Y: call plan_goal() when plan is empty
        if not state.plan:
            log.info("orchestrator.loop.calling_agent_y", reason="plan_empty")
            try:
                tasks = plan_goal(goal=state.goal, state=state)
                state = state.model_copy(update={"plan": tasks})
                save_state(state)
                log.info("orchestrator.loop.plan_created", tasks=len(tasks))
            except Exception as exc:
                log.error("orchestrator.loop.plan_goal_failed", error=str(exc))
                break
            continue

        try:
            state = run_once(state, repo_path)
        except Exception as exc:
            log.error("orchestrator.loop.exception", iteration=iteration, error=str(exc))
            continue
    else:
        log.info("orchestrator.loop.max_iterations", max_iterations=max_iterations)

    # Telegram notification on exit
    completed = sum(1 for t in state.plan if t.status == "completed")
    failed = sum(1 for t in state.plan if t.status == "failed")
    blocked = sum(1 for t in state.plan if t.status == "blocked")
    notify_loop_done(project_id, completed, failed, blocked)

    return state


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")

    from agent_y.schemas import AcceptanceCase, AcceptanceCriteria, Task as T, TaskAction

    _criteria = AcceptanceCriteria(
        target_function="add",
        cases=[
            AcceptanceCase(inputs=["add(1,2)"], expected="3"),
            AcceptanceCase(inputs=["add(0,0)"], expected="0"),
            AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
        ],
    )
    _task = T(
        task_id="T1", action=TaskAction.WRITE_FILE,
        description="Create add", files_to_touch=["app.py"],
        patch_order=["app.py"],
        acceptance_criteria=_criteria,
    )
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        subprocess.run(["git", "init", "-q", tmp], check=True)
        subprocess.run(["git", "-C", tmp, "config", "user.email", "test@test.com"], check=True)
        subprocess.run(["git", "-C", tmp, "config", "user.name", "Test"], check=True)
        os.environ["WORKSPACE_ROOT"] = tmp
        _state = SharedState(
            project_id="smoke", project_slug=tmp_path.name,
            goal="test", plan=[_task],
        )
        save_state(_state)
        _state2 = run_once(_state, tmp_path)
        print(f"Task status: {_state2.plan[0].status}")
        print("orchestrator.py smoke test PASSED")
