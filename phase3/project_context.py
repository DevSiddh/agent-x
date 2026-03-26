"""
phase3/project_context.py
v3.1 — Per-project .agent/context.md writer.
Every project gets .agent/context.md committed to GitHub alongside code.
Orchestrator appends after every completed task.
When resuming: read this FIRST before any code file.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent_y.schemas import SharedState, Task

log = structlog.get_logger()

REGISTRY_PATH = _REPO_ROOT / "memory" / "registry.jsonl"
CONTEXT_FILE = ".agent/context.md"


def scaffold_context(state: SharedState, repo_path: Path) -> None:
    """
    Create .agent/context.md for a new project.
    Called once when Orchestrator starts a new project.
    Never raises.
    """
    try:
        context_path = repo_path / CONTEXT_FILE
        if context_path.exists():
            return  # already scaffolded — don't overwrite on resume
        context_path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            f"# Agent-XYZ Project Context\n\n"
            f"## Goal\n{state.goal}\n\n"
            f"## Architecture\n_To be filled as tasks complete._\n\n"
            f"## Key Files\n_None yet._\n\n"
            f"## Decisions\n_None yet._\n\n"
            f"## Known Issues\n_None yet._\n\n"
            f"## Last Task\n_None yet._\n\n"
            f"---\n_Created: {_now()}_\n"
        )
        context_path.write_text(content, encoding="utf-8")
        log.info("project_context.scaffold", project=state.project_slug)
    except Exception as exc:
        log.error("project_context.scaffold_error", error=str(exc))


def append_task(state: SharedState, task: Task, repo_path: Path) -> None:
    """
    Append completed task info to .agent/context.md.
    Updates: Last task + Key files section.
    Never raises.
    """
    try:
        context_path = repo_path / CONTEXT_FILE
        if not context_path.exists():
            scaffold_context(state, repo_path)

        text = context_path.read_text(encoding="utf-8")

        # Update Last Task
        last_task_line = f"_Last task: `{task.task_id}` — {task.description} ({_now()})_"
        if "## Last Task" in text:
            lines = text.splitlines()
            new_lines = []
            skip_next = False
            for line in lines:
                if line.strip() == "## Last Task":
                    new_lines.append(line)
                    new_lines.append(last_task_line)
                    skip_next = True
                elif skip_next and line.startswith("_"):
                    skip_next = False  # replace old value
                else:
                    skip_next = False
                    new_lines.append(line)
            text = "\n".join(new_lines)
        else:
            text += f"\n## Last Task\n{last_task_line}\n"

        # Update Key Files — dedup: only add files not already listed
        import re as _re
        existing_files = set(_re.findall(r"`([^`]+)`", text))
        for f in task.files_to_touch:
            if f not in existing_files:
                text = text.replace(
                    "## Key Files\n_None yet._",
                    f"## Key Files\n- `{f}`",
                )
                text = text.replace(
                    "## Key Files\n",
                    f"## Key Files\n- `{f}`\n",
                )
                existing_files.add(f)

        context_path.write_text(text, encoding="utf-8")
        log.info("project_context.appended", task_id=task.task_id, project=state.project_slug)
    except Exception as exc:
        log.error("project_context.append_error", error=str(exc))


def read_context(repo_path: Path) -> str:
    """
    Read .agent/context.md for a project. Returns "" if missing.
    Never raises.
    """
    try:
        p = repo_path / CONTEXT_FILE
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except Exception as exc:
        log.error("project_context.read_error", error=str(exc))
        return ""


# ---------------------------------------------------------------------------
# Registry — index of all projects
# ---------------------------------------------------------------------------

def register_project(state: SharedState) -> None:
    """
    Append project to registry.jsonl. Skips if already registered.
    Never raises.
    """
    try:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Check if already exists
        if REGISTRY_PATH.exists():
            with open(REGISTRY_PATH, encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    if entry.get("project_slug") == state.project_slug:
                        return  # already registered
        entry = {
            "project_id": state.project_id,
            "project_slug": state.project_slug,
            "goal": state.goal[:120],
            "status": "active",
            "created_at": _now(),
            "last_task": None,
        }
        with open(REGISTRY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        log.info("registry.registered", project=state.project_slug)
    except Exception as exc:
        log.error("registry.register_error", error=str(exc))


def update_registry_status(project_slug: str, status: str) -> None:
    """
    Update status field for a project in registry.jsonl.
    Valid statuses: active | completed | deleted | failed
    Never raises.
    """
    try:
        if not REGISTRY_PATH.exists():
            return
        lines = REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
        updated = []
        for line in lines:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("project_slug") == project_slug:
                entry["status"] = status
            updated.append(json.dumps(entry))
        REGISTRY_PATH.write_text("\n".join(updated) + "\n", encoding="utf-8")
        log.info("registry.status_updated", project=project_slug, status=status)
    except Exception as exc:
        log.error("registry.status_update_error", error=str(exc))


def update_registry_last_task(project_slug: str, task_id: str) -> None:
    """Update last_task field for a project in registry.jsonl. Never raises."""
    try:
        if not REGISTRY_PATH.exists():
            return
        lines = REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
        updated = []
        for line in lines:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("project_slug") == project_slug:
                entry["last_task"] = task_id
            updated.append(json.dumps(entry))
        REGISTRY_PATH.write_text("\n".join(updated) + "\n", encoding="utf-8")
    except Exception as exc:
        log.error("registry.update_error", error=str(exc))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    import tempfile, os
    from agent_y.schemas import AcceptanceCase, AcceptanceCriteria, TaskAction

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        os.environ["WORKSPACE_ROOT"] = tmp

        criteria = AcceptanceCriteria(
            target_function="add",
            cases=[
                AcceptanceCase(inputs=["add(1,2)"], expected="3"),
                AcceptanceCase(inputs=["add(0,0)"], expected="0"),
                AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
            ],
        )
        task = Task(
            task_id="T1", action=TaskAction.WRITE_FILE,
            description="Create add function", files_to_touch=["src/add.py"],
            acceptance_criteria=criteria,
        )
        state = SharedState(
            project_id="smoke", project_slug="smoke-proj",
            goal="Build a calculator", plan=[task],
        )

        scaffold_context(state, tmp_path)
        assert (tmp_path / CONTEXT_FILE).exists()

        append_task(state, task, tmp_path)
        content = read_context(tmp_path)
        assert "T1" in content
        assert "src/add.py" in content

        register_project(state)
        register_project(state)  # idempotent
        assert REGISTRY_PATH.exists()
        lines = REGISTRY_PATH.read_text().strip().splitlines()
        assert len(lines) == 1  # no duplicate

        update_registry_last_task("smoke-proj", "T1")
        entry = json.loads(REGISTRY_PATH.read_text().strip().splitlines()[0])
        assert entry["last_task"] == "T1"

        print("project_context.py smoke test PASSED")
