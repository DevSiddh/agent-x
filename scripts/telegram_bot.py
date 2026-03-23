"""
Telegram bot bridge for Agent-X / Claude Code on VPS.

Usage (on VPS):
    python scripts/telegram_bot.py

Commands (from phone):
    /step E1          → run "step E1" in Claude Code
    /step C3b         → run "step C3b"
    /audit            → run audit
    /status           → show last 20 lines of progress.md
    /memory N         → show last N memory entries (default 5)
    /ps               → show running Claude processes
    /kill             → kill running Claude session
    /schedule C4 02:00  → run step C4 at 2:00 AM tonight
    /schedules          → list all scheduled steps
    /unschedule C4      → cancel scheduled step C4
    /help             → command list

Env vars required (in .env):
    TELEGRAM_BOT_TOKEN   — from @BotFather
    TELEGRAM_CHAT_ID     — your personal chat ID (from @userinfobot)
    AGENT_X_DIR          — absolute path to agent-x project root on VPS
    ANTHROPIC_API_KEY    — for Claude Code
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import structlog
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

log = structlog.get_logger()

# ── Config ──────────────────────────────────────────────────────────────────

def _require_env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        print(f"ERROR: {key} not set in .env", file=sys.stderr)
        sys.exit(1)
    return val


BOT_TOKEN    = _require_env("TELEGRAM_BOT_TOKEN")
CHAT_ID      = int(_require_env("TELEGRAM_CHAT_ID"))
PROJECT_DIR  = Path(_require_env("AGENT_X_DIR"))
MAX_LEN      = 3800   # Telegram limit is 4096 — leave headroom
PROGRESS_MD  = PROJECT_DIR / "docs" / "progress.md"
MEMORY_JSONL = PROJECT_DIR / "memory" / "memory.jsonl"

# Singleton running process
_current_proc: Optional[asyncio.subprocess.Process] = None
_current_task: Optional[asyncio.Task] = None

# Scheduled steps: step_name → asyncio.Task
_scheduled: dict[str, asyncio.Task] = {}


# ── Auth ─────────────────────────────────────────────────────────────────────

def _authorized(update: Update) -> bool:
    return update.effective_chat.id == CHAT_ID


async def _deny(update: Update) -> None:
    await update.message.reply_text("Unauthorized.")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _chunk(text: str, size: int = MAX_LEN) -> list[str]:
    """Split text into Telegram-safe chunks."""
    return [text[i : i + size] for i in range(0, max(len(text), 1), size)]


async def _send(update: Update, text: str) -> None:
    """Send potentially long text, split into chunks."""
    for chunk in _chunk(text):
        await update.message.reply_text(chunk)


async def _run_claude(prompt: str, update: Update) -> None:
    """
    Run claude non-interactively, stream stdout back to Telegram.
    Uses --dangerously-skip-permissions so it runs unattended.
    """
    global _current_proc, _current_task

    if _current_proc is not None and _current_proc.returncode is None:
        await update.message.reply_text(
            "A Claude session is already running. Use /kill to stop it first."
        )
        return

    await update.message.reply_text(f"Started: `{prompt}`", parse_mode=ParseMode.MARKDOWN_V2)

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    _current_proc = await asyncio.create_subprocess_exec(
        "claude",
        "--dangerously-skip-permissions",
        "-p", prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(PROJECT_DIR),
        env=env,
    )

    output_lines: list[str] = []
    flush_buffer: list[str] = []

    async def flush_to_telegram() -> None:
        if flush_buffer:
            chunk_text = "".join(flush_buffer)
            flush_buffer.clear()
            await _send(update, chunk_text)

    try:
        async for raw in _current_proc.stdout:
            line = raw.decode(errors="replace")
            output_lines.append(line)
            flush_buffer.append(line)
            # Send update every ~80 lines so you see progress
            if len(flush_buffer) >= 80:
                await flush_to_telegram()

        await flush_to_telegram()
        await _current_proc.wait()

    except asyncio.CancelledError:
        _current_proc.send_signal(signal.SIGTERM)
        await update.message.reply_text("Session cancelled.")
        return

    rc = _current_proc.returncode
    status_emoji = "DONE" if rc == 0 else f"FAILED (exit {rc})"
    await update.message.reply_text(f"{status_emoji} — {prompt}")
    _current_proc = None


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    if not context.args:
        await update.message.reply_text("Usage: /step E1  or  /step C3b  etc.")
        return
    step_name = " ".join(context.args)
    prompt = f"step {step_name}"
    asyncio.create_task(_run_claude(prompt, update))


async def cmd_audit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    asyncio.create_task(_run_claude("audit", update))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    if not PROGRESS_MD.exists():
        await update.message.reply_text("progress.md not found.")
        return
    lines = PROGRESS_MD.read_text(encoding="utf-8").splitlines()
    # Show first 5 lines (header/status) + last 30 lines (recent activity)
    header = lines[:6]
    recent = lines[-30:]
    text = "\n".join(header) + "\n...\n" + "\n".join(recent)
    await _send(update, text)


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    n = 5
    if context.args:
        try:
            n = int(context.args[0])
        except ValueError:
            pass
    if not MEMORY_JSONL.exists():
        await update.message.reply_text("memory.jsonl not found.")
        return
    lines = MEMORY_JSONL.read_text(encoding="utf-8").splitlines()
    last_n = lines[-n:] if len(lines) >= n else lines
    entries = []
    for line in last_n:
        try:
            e = json.loads(line)
            entries.append(
                f"[{e.get('decision','?')}] {e.get('bug_signature','?')} "
                f"({e.get('repo','?')})"
            )
        except json.JSONDecodeError:
            entries.append(line[:120])
    await _send(update, "\n".join(entries) or "No entries.")


async def cmd_ps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    result = subprocess.run(
        ["ps", "aux"],
        capture_output=True, text=True
    )
    lines = [l for l in result.stdout.splitlines() if "claude" in l.lower()]
    text = "\n".join(lines) if lines else "No Claude processes found."
    await _send(update, text)


async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    global _current_proc
    if _current_proc is None or _current_proc.returncode is not None:
        await update.message.reply_text("No active Claude session.")
        return
    _current_proc.send_signal(signal.SIGTERM)
    await update.message.reply_text("Sent SIGTERM to running Claude session.")


async def _wait_and_run(step: str, hour: int, minute: int, update: Update) -> None:
    """Wait until target time then run the step."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    wait_secs = (target - now).total_seconds()
    hours_away = wait_secs / 3600
    await update.message.reply_text(
        f"Scheduled: step {step} at {hour:02d}:{minute:02d} (in {hours_away:.1f}h)"
    )
    try:
        await asyncio.sleep(wait_secs)
        await update.message.reply_text(f"Starting scheduled step {step}...")
        await _run_claude(f"step {step}", update)
    except asyncio.CancelledError:
        await update.message.reply_text(f"Cancelled: step {step}")
    finally:
        _scheduled.pop(step, None)


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /schedule C4 02:00")
        return
    step_name = context.args[0].upper()
    time_str = context.args[1]
    try:
        t = datetime.strptime(time_str, "%H:%M")
        hour, minute = t.hour, t.minute
    except ValueError:
        await update.message.reply_text("Invalid time format. Use HH:MM e.g. 02:00")
        return
    if step_name in _scheduled:
        await update.message.reply_text(
            f"Step {step_name} already scheduled. Use /unschedule {step_name} first."
        )
        return
    task = asyncio.create_task(_wait_and_run(step_name, hour, minute, update))
    _scheduled[step_name] = task


async def cmd_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    if not _scheduled:
        await update.message.reply_text("No scheduled steps.")
        return
    lines = [f"step {name}" for name in _scheduled]
    await update.message.reply_text("Scheduled:\n" + "\n".join(lines))


async def cmd_unschedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    if not context.args:
        await update.message.reply_text("Usage: /unschedule C4")
        return
    step_name = context.args[0].upper()
    task = _scheduled.get(step_name)
    if task is None:
        await update.message.reply_text(f"No scheduled step: {step_name}")
        return
    task.cancel()
    await update.message.reply_text(f"Cancelled: step {step_name}")


async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward any non-command message to Claude and reply with the output."""
    if not _authorized(update):
        await _deny(update)
        return
    message = update.message.text.strip()
    if not message:
        return
    await update.message.reply_text("Thinking...")
    asyncio.create_task(_run_claude(message, update))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await _deny(update)
        return
    text = (
        "Agent-X Telegram Bot\n\n"
        "/step E1            — run step E1 (or any step name)\n"
        "/audit              — run audit\n"
        "/status             — show progress.md summary\n"
        "/memory 10          — show last N memory entries\n"
        "/ps                 — show running Claude processes\n"
        "/kill               — kill active Claude session\n"
        "/schedule C4 02:00  — run step C4 at 2:00 AM tonight\n"
        "/schedules          — list all scheduled steps\n"
        "/unschedule C4      — cancel scheduled step C4\n"
        "/help               — this message\n"
    )
    await update.message.reply_text(text)


# ── Boot ─────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("telegram_bot.starting", project_dir=str(PROJECT_DIR))

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("step",   cmd_step))
    app.add_handler(CommandHandler("audit",  cmd_audit))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("ps",          cmd_ps))
    app.add_handler(CommandHandler("kill",        cmd_kill))
    app.add_handler(CommandHandler("schedule",    cmd_schedule))
    app.add_handler(CommandHandler("schedules",   cmd_schedules))
    app.add_handler(CommandHandler("unschedule",  cmd_unschedule))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("start",       cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_chat))

    log.info("telegram_bot.polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
