"""
phase3/brief_watcher.py
File watcher — drop brief.yaml into /projects/new/ → triggers Agent-XYZ.
Requires: pip install watchdog pyyaml
Run: python phase3/brief_watcher.py
"""

import os
import sys
import time
from pathlib import Path

import structlog
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

log = structlog.get_logger()

INTAKE_DIR = _REPO_ROOT / "projects" / "new"


def _parse_brief(brief_path: Path) -> dict:
    """Parse brief.yaml → dict. Returns {} on failure."""
    try:
        import yaml
        with open(brief_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        log.error("brief_watcher.parse_error", file=str(brief_path), error=str(exc))
        return {}


def _trigger_orchestrator(brief: dict, brief_path: Path) -> None:
    """Bootstrap SharedState from brief and hand off to Orchestrator."""
    try:
        from agent_y.schemas import SharedState
        from phase3.orchestrator import run_loop
        from phase3.state_manager import save_state

        project_id = brief.get("project_id") or brief_path.stem
        goal = brief.get("goal", "No goal specified")
        workspace = Path(os.environ.get("WORKSPACE_ROOT", str(_REPO_ROOT / "projects")))

        state = SharedState(
            project_id=project_id,
            project_slug=project_id,
            goal=goal,
            plan=[],
        )
        save_state(state)
        log.info("brief_watcher.triggered", project_id=project_id, goal=goal[:80])

        # Move brief out of intake to avoid re-processing
        processed = brief_path.parent / "processed"
        processed.mkdir(exist_ok=True)
        brief_path.rename(processed / brief_path.name)

        run_loop(project_id, goal, workspace / project_id)
    except Exception as exc:
        log.error("brief_watcher.trigger_error", error=str(exc))


def _handle_new_file(path: Path) -> None:
    """Called when a new file lands in /projects/new/."""
    if path.suffix not in (".yaml", ".yml"):
        log.info("brief_watcher.ignored", file=path.name)
        return
    log.info("brief_watcher.detected", file=path.name)
    brief = _parse_brief(path)
    if not brief:
        return
    _trigger_orchestrator(brief, path)


def watch() -> None:
    """Start watchdog observer on INTAKE_DIR. Blocking."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        log.error("brief_watcher.missing_dep", msg="pip install watchdog pyyaml")
        return

    class _Handler(FileSystemEventHandler):
        def on_created(self, event):  # type: ignore
            if not event.is_directory:
                _handle_new_file(Path(event.src_path))

    INTAKE_DIR.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(_Handler(), str(INTAKE_DIR), recursive=False)
    observer.start()
    log.info("brief_watcher.started", watching=str(INTAKE_DIR))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    watch()
