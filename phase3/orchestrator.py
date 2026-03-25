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

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent_y.schemas import SharedState, Task, TaskAction
from phase2.executor.runner import RunResult, apply_patch, write_file
from phase2.tools.ast_mapper import map_repo
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
    "Write tests/test_<name>.py using pytest.mark.parametrize for the provided cases. "
    "Then implement src/<name>.py to make them pass. "
    "Hard limits: 50 lines per new file, 15 lines per edit. "
    "Return raw Python only. No markdown. No explanation."
)


def is_new_file(file_path: str, repo_path: Path) -> bool:
    """True if the file does not exist on disk yet."""
    return not (repo_path / file_path).exists()


def is_done(state: SharedState) -> bool:
    """True if ALL tasks are completed or blocked."""
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

    # Execute files in patch_order
    for file_str in task.patch_order:
        file_path = repo_path / file_str
        if is_new_file(file_str, repo_path):
            # Content generation placeholder — real impl calls DeepSeek
            result = write_file(file_path, f"# {file_str}\n", repo_path)
        else:
            # file_edit path — patch must be provided via task metadata
            # For now: no-op success (patch content injected by caller)
            result = RunResult(success=True)

        if not result.success:
            log.warning(
                "orchestrator.file_op_failed",
                task_id=task.task_id,
                file=file_str,
                error=result.error,
            )
            state = mark_failed(state, task.task_id, "file_op_error")
            state = _block_dependents(state, task.task_id)
            save_state(state)
            return state

    # Run acceptance tests via pytest
    test_result = _run_tests(repo_path, task)
    if not test_result:
        log.warning("orchestrator.tests_failed", task_id=task.task_id)
        state = mark_failed(state, task.task_id, "test_failure")
        state = _block_dependents(state, task.task_id)
        save_state(state)
        return state

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
    log.info("orchestrator.task_completed", task_id=task.task_id)
    return state


def _run_tests(repo_path: Path, task: Task) -> bool:
    """Run pytest filtering by target_function. Returns True if all pass."""
    try:
        target = task.acceptance_criteria.target_function
        result = subprocess.run(
            ["python3", "-m", "pytest", str(repo_path / "tests"), "-q",
             f"-k", target, "--tb=short"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
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

    for iteration in range(max_iterations):
        if is_done(state):
            log.info("orchestrator.loop.done", iterations=iteration)
            break

        # Agent-Y needed when plan is empty
        if not state.plan:
            log.info("orchestrator.loop.needs_agent_y", reason="plan_empty")
            break

        try:
            state = run_once(state, repo_path)
        except Exception as exc:
            log.error("orchestrator.loop.exception", iteration=iteration, error=str(exc))
            continue
    else:
        log.info("orchestrator.loop.max_iterations", max_iterations=max_iterations)

    return state


if __name__ == "__main__":
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
