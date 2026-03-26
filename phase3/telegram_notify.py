"""
phase3/telegram_notify.py
Send a Telegram message when run_loop() completes. Never raises.
Uses requests (already in requirements.txt) — no bot library needed.
"""
import os
from typing import Optional

import requests
import structlog

log = structlog.get_logger()


def _get_config() -> tuple[str, str]:
    """Return (bot_token, chat_id). Raises EnvironmentError if missing."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
    return token, chat_id


def send(message: str) -> None:
    """Send a plain-text message to the configured Telegram chat. Never raises."""
    try:
        token, chat_id = _get_config()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        if resp.status_code == 200:
            log.info("telegram_notify.sent", chars=len(message))
        else:
            log.warning("telegram_notify.failed", status=resp.status_code, body=resp.text[:200])
    except EnvironmentError:
        log.warning("telegram_notify.skipped", reason="token or chat_id not set")
    except Exception as exc:
        log.warning("telegram_notify.error", error=str(exc))


def notify_loop_done(project_id: str, completed: int, failed: int, blocked: int) -> None:
    """Send loop completion summary to Telegram."""
    status = "✅ DONE" if failed == 0 and blocked == 0 else "⚠️ PARTIAL"
    msg = (
        f"{status} — {project_id}\n"
        f"Tasks: {completed} completed, {failed} failed, {blocked} blocked"
    )
    send(msg)


def notify_loop_failed(project_id: str, error: str) -> None:
    """Send loop failure alert to Telegram."""
    send(f"❌ FAILED — {project_id}\nError: {error[:200]}")
