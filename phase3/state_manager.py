"""
phase3/state_manager.py
Atomic state persistence for Agent-X v3.0 Orchestrator.
Handles load/save of SharedState + task status transitions.
Never raises — all errors logged and state returned unchanged.
"""

import sys
from pathlib import Path

import structlog

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent_y.schemas import SharedState, Task

log = structlog.get_logger()

STATE_PATH = _REPO_ROOT / "memory" / "state.json"
TEMP_PATH  = _REPO_ROOT / "memory" / "state_tmp.json"


def load_state() -> SharedState | None:
    """Load state.json → parse as SharedState. Return None if missing."""
    try:
        if not STATE_PATH.exists():
            log.info("state_manager.load.missing")
            return None
        data = STATE_PATH.read_text(encoding="utf-8")
        state = SharedState.model_validate_json(data)
        log.info("state_manager.load.ok", project_id=state.project_id)
        return state
    except Exception as exc:
        log.error("state_manager.load.error", error=str(exc))
        return None


def save_state(state: SharedState) -> None:
    """
    Atomic write — crash-safe, never corrupts state.json.
    1. Write to state_tmp.json
    2. Rename TEMP_PATH → STATE_PATH (atomic on Linux/Mac)
    Never direct json.dump to state.json — always via temp + rename.
    """
    try:
        TEMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        TEMP_PATH.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        # Windows-safe atomic replace (os.replace is atomic on POSIX, near-atomic on Windows)
        import os as _os
        _os.replace(str(TEMP_PATH), str(STATE_PATH))
        log.info("state_manager.save.ok", project_id=state.project_id)
    except Exception as exc:
        log.error("state_manager.save.error", error=str(exc))


def get_next_pending_task(state: SharedState) -> Task | None:
    """Return first pending task where all depends_on are completed."""
    completed = {t.task_id for t in state.plan if t.status == "completed"}
    for task in state.plan:
        if task.status != "pending":
            continue
        if all(dep in completed for dep in task.depends_on):
            log.info("state_manager.next_task", task_id=task.task_id)
            return task
    log.info("state_manager.no_pending_tasks")
    return None


def mark_in_progress(state: SharedState, task_id: str) -> SharedState:
    """Set task status = 'in_progress'. Returns updated state. Does NOT save."""
    try:
        updated = []
        for t in state.plan:
            if t.task_id == task_id:
                updated.append(t.model_copy(update={"status": "in_progress"}))
            else:
                updated.append(t)
        state = state.model_copy(update={"plan": updated, "current_task_id": task_id})
        log.info("state_manager.mark_in_progress", task_id=task_id)
    except Exception as exc:
        log.error("state_manager.mark_in_progress.error", task_id=task_id, error=str(exc))
    return state


def mark_completed(state: SharedState, task_id: str) -> SharedState:
    """Set task status = 'completed', failed_task_streak = 0."""
    try:
        updated = []
        for t in state.plan:
            if t.task_id == task_id:
                updated.append(t.model_copy(update={"status": "completed"}))
            else:
                updated.append(t)
        state = state.model_copy(update={"plan": updated, "failed_task_streak": 0})
        log.info("state_manager.mark_completed", task_id=task_id)
    except Exception as exc:
        log.error("state_manager.mark_completed.error", task_id=task_id, error=str(exc))
    return state


def mark_failed(state: SharedState, task_id: str, failure_type: str) -> SharedState:
    """Set task status = 'failed', increment failed_attempts + failed_task_streak."""
    try:
        updated = []
        for t in state.plan:
            if t.task_id == task_id:
                updated.append(t.model_copy(update={
                    "status": "failed",
                    "failed_attempts": t.failed_attempts + 1,
                }))
            else:
                updated.append(t)
        state = state.model_copy(update={
            "plan": updated,
            "failed_task_streak": state.failed_task_streak + 1,
        })
        log.info("state_manager.mark_failed", task_id=task_id, failure_type=failure_type)
    except Exception as exc:
        log.error("state_manager.mark_failed.error", task_id=task_id, error=str(exc))
    return state


def mark_blocked(state: SharedState, task_id: str) -> SharedState:
    """Set task status = 'blocked' — dependency failed, cannot proceed."""
    try:
        updated = []
        for t in state.plan:
            if t.task_id == task_id:
                updated.append(t.model_copy(update={"status": "blocked"}))
            else:
                updated.append(t)
        state = state.model_copy(update={"plan": updated})
        log.info("state_manager.mark_blocked", task_id=task_id)
    except Exception as exc:
        log.error("state_manager.mark_blocked.error", task_id=task_id, error=str(exc))
    return state


if __name__ == "__main__":
    from agent_y.schemas import AcceptanceCase, AcceptanceCriteria, TaskAction

    _criteria = AcceptanceCriteria(
        target_function="add",
        cases=[
            AcceptanceCase(inputs=["add(1,2)"], expected="3"),
            AcceptanceCase(inputs=["add(0,0)"], expected="0"),
            AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
        ],
    )
    from agent_y.schemas import Task as T
    _task = T(
        task_id="T1", action=TaskAction.WRITE_FILE,
        description="Create add", files_to_touch=["app.py"],
        acceptance_criteria=_criteria,
    )
    _state = SharedState(
        project_id="test", project_slug="test-proj",
        goal="Build calculator", plan=[_task],
    )
    save_state(_state)
    loaded = load_state()
    assert loaded is not None
    assert loaded.project_id == "test"
    nxt = get_next_pending_task(loaded)
    assert nxt is not None and nxt.task_id == "T1"
    print("state_manager.py smoke test PASSED")
