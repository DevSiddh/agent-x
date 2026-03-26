"""
phase3/telegram_bot.py
State-aware Telegram bot.
  Route A — blocked project waiting for user → resume with reply
  Route B — no blocked project → apply universal template → new build
Run: python phase3/telegram_bot.py
"""
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import requests
import structlog
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

log = structlog.get_logger()
INTAKE_DIR = _REPO_ROOT / "projects" / "new"
SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".pdf", ".csv", ".json", ".py", ".js", ".md"}
REGISTRY_PATH = _REPO_ROOT / "memory" / "registry.jsonl"
STATE_PATH = _REPO_ROOT / "memory" / "state.json"
PENDING_SPEC_PATH = _REPO_ROOT / "memory" / "pending_spec.json"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _get_config() -> tuple[str, str]:
    """Return (bot_token, chat_id). Raises EnvironmentError if missing."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
    return token, chat_id


def _slugify(text: str) -> str:
    """Convert goal text to a safe project slug (max 40 chars)."""
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return slug[:40].strip("_") or "project"


def _reply(token: str, chat_id: str, text: str) -> None:
    """Send a reply message. Never raises."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as exc:
        log.warning("telegram_bot.reply_error", error=str(exc))


# ---------------------------------------------------------------------------
# Router helpers
# ---------------------------------------------------------------------------

def get_blocked_project() -> dict | None:
    """Return the first registry entry with status=blocked_waiting_for_user, or None."""
    if not REGISTRY_PATH.exists():
        return None
    for line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if entry.get("status") == "blocked_waiting_for_user":
                return entry
        except json.JSONDecodeError:
            continue
    return None


def apply_universal_template(raw_text: str) -> str:
    """Wrap raw user text into a structured goal Agent-Y understands."""
    return (
        f"Project goal: {raw_text}\n\n"
        "Requirements:\n"
        "- Write tests first, then implementation\n"
        "- Flat file structure (no subdirectories)\n"
        "- All functions individually testable\n"
        "- Handle edge cases and error conditions\n"
        "- Python only unless goal explicitly requires another language"
    )


def resume_project(token: str, chat_id: str, project_slug: str, user_reply: str) -> None:
    """Handle user reply to a blocked project.

    Two sub-cases:
    A) Pending spec — spec answers collected → combine with original goal → create brief → build
    B) Mid-build blocked — append clarification to state → re-run loop
    """
    pending = _load_pending_spec()

    if pending and pending.get("project_id") == project_slug:
        # Sub-case A: spec collection complete → launch build
        original_goal = pending["goal"]
        full_goal = apply_universal_template(
            f"{original_goal}\n\nUser specs: {user_reply}"
        )
        _clear_pending_spec()
        INTAKE_DIR.mkdir(parents=True, exist_ok=True)
        brief = {"project_id": project_slug, "goal": full_goal}
        (INTAKE_DIR / f"{project_slug}.yaml").write_text(yaml.dump(brief), encoding="utf-8")
        log.info("telegram_bot.spec_collected", project_id=project_slug)
        _reply(token, chat_id,
               f"▶️ Perfect. Building *{project_slug}*...\n"
               f"Goal: {original_goal[:80]}\nSpecs: {user_reply[:80]}")
        return

    # Sub-case B: mid-build clarification
    try:
        from phase3.project_context import update_registry_status
        from phase3.state_manager import load_state, save_state
        from phase3.orchestrator import run_loop

        state = load_state()
        if state is None or state.project_slug != project_slug:
            _reply(token, chat_id, f"❌ Could not load state for {project_slug}.")
            return

        updated_goal = f"{state.goal}\n\nUser clarification: {user_reply}"
        state = state.model_copy(update={"goal": updated_goal})
        save_state(state)
        update_registry_status(project_slug, "active")
        log.info("telegram_bot.resuming", project_slug=project_slug)
        _reply(token, chat_id, f"▶️ Received. Resuming {project_slug}...")

        workspace = Path(os.environ.get("WORKSPACE_ROOT", str(_REPO_ROOT / "projects")))
        repo_path = workspace / project_slug

        def _run() -> None:
            run_loop(state.project_id, updated_goal, repo_path)

        threading.Thread(target=_run, daemon=True).start()

    except Exception as exc:
        log.error("telegram_bot.resume_error", error=str(exc))
        _reply(token, chat_id, f"❌ Resume failed: {exc}")


def _save_pending_spec(goal: str, slug: str) -> None:
    """Persist the pending goal so resume can find it after bot restart."""
    PENDING_SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_SPEC_PATH.write_text(
        json.dumps({"goal": goal, "project_id": slug}), encoding="utf-8"
    )


def _load_pending_spec() -> dict | None:
    """Return pending spec dict or None if not present."""
    if not PENDING_SPEC_PATH.exists():
        return None
    try:
        return json.loads(PENDING_SPEC_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clear_pending_spec() -> None:
    if PENDING_SPEC_PATH.exists():
        PENDING_SPEC_PATH.unlink()


def _set_registry_blocked(slug: str) -> None:
    """Write a registry entry for this slug with blocked_waiting_for_user status."""
    try:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Remove existing entry for this slug if present
        lines = []
        if REGISTRY_PATH.exists():
            for line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines():
                if line.strip() and json.loads(line).get("project_slug") != slug:
                    lines.append(line)
        import datetime
        entry = {
            "project_id": slug, "project_slug": slug, "goal": "",
            "status": "blocked_waiting_for_user",
            "created_at": datetime.date.today().isoformat(), "last_task": None,
        }
        lines.append(json.dumps(entry))
        REGISTRY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:
        log.warning("telegram_bot.registry_blocked_error", error=str(exc))


def start_new_project(token: str, chat_id: str, raw_text: str) -> None:
    """Ask 2 spec questions first, save pending goal, set blocked_waiting_for_user."""
    slug = _slugify(raw_text)
    _save_pending_spec(raw_text, slug)
    _set_registry_blocked(slug)
    log.info("telegram_bot.spec_requested", project_id=slug)
    _reply(token, chat_id,
           f"⚙️ Got it. Quick specs needed for *{slug}*:\n\n"
           f"1. Separate new project or improve existing code?\n"
           f"2. Any specific requirements / tech stack? (or type 'none')\n\n"
           f"Reply with both answers and I'll start building.")


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

def handle_text(token: str, chat_id: str, text: str) -> None:
    """State-aware router: resume blocked project OR start new one."""
    blocked = get_blocked_project()
    if blocked:
        resume_project(token, chat_id, blocked["project_slug"], text)
    else:
        start_new_project(token, chat_id, text)


def handle_document(token: str, chat_id: str, document: dict) -> None:
    """Download uploaded file → intake dir. YAML goes direct; others get companion YAML."""
    file_name: str = document.get("file_name", "upload")
    file_id: str = document.get("file_id", "")
    suffix = Path(file_name).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        _reply(token, chat_id, f"⚠️ Unsupported file type: {suffix}")
        return

    resp = requests.get(
        f"https://api.telegram.org/bot{token}/getFile",
        params={"file_id": file_id},
        timeout=10,
    )
    file_path = resp.json().get("result", {}).get("file_path", "")
    if not file_path:
        _reply(token, chat_id, "❌ Could not fetch file from Telegram.")
        return

    content = requests.get(
        f"https://api.telegram.org/file/bot{token}/{file_path}",
        timeout=30,
    ).content

    INTAKE_DIR.mkdir(parents=True, exist_ok=True)
    (INTAKE_DIR / file_name).write_bytes(content)

    if suffix in (".yaml", ".yml"):
        log.info("telegram_bot.yaml_dropped", file=file_name)
        _reply(token, chat_id, f"📄 Brief received: {file_name}\nStarting build...")
    else:
        slug = _slugify(Path(file_name).stem)
        brief = {"project_id": slug,
                 "goal": apply_universal_template(f"Process uploaded file: {file_name}"),
                 "attachments": [file_name]}
        (INTAKE_DIR / f"{slug}.yaml").write_text(yaml.dump(brief), encoding="utf-8")
        log.info("telegram_bot.file_dropped", file=file_name, project_id=slug)
        _reply(token, chat_id, f"📎 File received: {file_name} → building: {slug}")


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------

def poll() -> None:
    """Long-poll Telegram for updates. Blocking."""
    token, chat_id = _get_config()
    offset = 0
    log.info("telegram_bot.started", chat_id=chat_id)

    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35,
            )
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                if msg.get("text"):
                    handle_text(token, chat_id, msg["text"])
                elif msg.get("document"):
                    handle_document(token, chat_id, msg["document"])
        except Exception as exc:
            log.warning("telegram_bot.poll_error", error=str(exc))
            time.sleep(2)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
    poll()
