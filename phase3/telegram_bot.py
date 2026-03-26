"""
phase3/telegram_bot.py
Telegram bot — receives text/files → drops into projects/new/ → brief_watcher triggers build.
Run: python phase3/telegram_bot.py
"""
import os
import re
import sys
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


def handle_text(token: str, chat_id: str, text: str) -> None:
    """Convert text message → brief.yaml → intake dir."""
    slug = _slugify(text)
    brief = {"project_id": slug, "goal": text}
    INTAKE_DIR.mkdir(parents=True, exist_ok=True)
    out = INTAKE_DIR / f"{slug}.yaml"
    out.write_text(yaml.dump(brief), encoding="utf-8")
    log.info("telegram_bot.brief_created", project_id=slug)
    _reply(token, chat_id, f"⚙️ Building: {slug}\n{text[:100]}")


def handle_document(token: str, chat_id: str, document: dict) -> None:
    """Download uploaded file → intake dir. YAML goes direct; others get companion YAML."""
    file_name: str = document.get("file_name", "upload")
    file_id: str = document.get("file_id", "")
    suffix = Path(file_name).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        _reply(token, chat_id, f"⚠️ Unsupported file type: {suffix}")
        return

    # Resolve download URL
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
        brief = {"project_id": slug, "goal": f"Process uploaded file: {file_name}",
                 "attachments": [file_name]}
        (INTAKE_DIR / f"{slug}.yaml").write_text(yaml.dump(brief), encoding="utf-8")
        log.info("telegram_bot.file_dropped", file=file_name, project_id=slug)
        _reply(token, chat_id, f"📎 File received: {file_name} → building: {slug}")


def poll() -> None:
    """Long-poll Telegram for updates. Blocking — run in its own thread or process."""
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
