"""
phase3/plan_checkpoint.py
FIX-11 — Plan Checkpoint: show plan to user before build starts.

Four functions:
  detect_user_type(goal)        → "technical" | "general"
  format_plan_technical(plan)   → str
  format_plan_general(plan)     → str
  run_checkpoint(plan, state)   → bool  (always True — timeout = safe default)
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agent_y.schemas import SharedState, Task

log = structlog.get_logger()

TECHNICAL_KEYWORDS = {
    "fastapi", "flask", "sqlalchemy", "endpoint", "pytest", "pydantic",
    "async", "celery", "redis", "docker", "api", "crud", "orm", "migration",
    "webhook", "jwt", "auth", "middleware", "router", "schema", "model",
}


def detect_user_type(goal: str) -> str:
    """Return 'technical' if goal contains dev keywords, else 'general'."""
    words = set(goal.lower().split())
    return "technical" if words & TECHNICAL_KEYWORDS else "general"


def format_plan_technical(plan: list[Task]) -> str:
    """Compact plan for technical users — task IDs + files + descriptions."""
    lines = ["📋 *Build Plan* — reply ✅ to approve or ✏️ to change\n"]
    for t in plan:
        if t.action.value == "scaffold":
            lines.append(f"  `{t.task_id}` SCAFFOLD → {', '.join(t.files_to_touch)}")
        else:
            files = ", ".join(t.files_to_touch)
            req = "" if t.required else " _(optional)_"
            lines.append(f"  `{t.task_id}` {t.description[:55]}{req}\n       └ {files}")
    timeout_min = int(os.environ.get("PLAN_APPROVAL_TIMEOUT", "600")) // 60
    lines.append(f"\n⏱ No reply in {timeout_min} min → auto-approve and build")
    return "\n".join(lines)


def format_plan_general(plan: list[Task]) -> str:
    """Plain-language plan for non-technical users."""
    lines = ["🔨 *Here's what I'll build:*\n"]
    for t in plan:
        if t.action.value == "scaffold":
            continue  # hide scaffold from general users
        icon = "✅" if t.required else "🔵"
        label = "_(always built)_" if t.required else "_(optional)_"
        lines.append(f"  {icon} {t.description[:60]} {label}")
    timeout_min = int(os.environ.get("PLAN_APPROVAL_TIMEOUT", "600")) // 60
    lines.append(f"\nReply *yes* to build everything, or tell me what to skip.")
    lines.append(f"No reply in {timeout_min} min → building required tasks only.")
    return "\n".join(lines)


def run_checkpoint(plan: list[Task], state: SharedState) -> bool:
    """
    Send plan to Telegram, wait for approval.
    Returns True always — timeout = auto-approve (safe default).
    On timeout: optional tasks (required=False) are skipped.
    Max 3 change loops before auto-approving.
    """
    from phase3.telegram_notify import send

    timeout = int(os.environ.get("PLAN_APPROVAL_TIMEOUT", "600"))
    user_type = detect_user_type(state.goal)

    if user_type == "technical":
        msg = format_plan_technical(plan)
    else:
        msg = format_plan_general(plan)

    send(msg)
    log.info("plan_checkpoint.sent", user_type=user_type, tasks=len(plan), timeout=timeout)

    # Poll interrupt_queue for approval (FIX-12 queue reused here)
    deadline = time.time() + timeout
    change_loops = 0

    while time.time() < deadline and change_loops < 3:
        # Reload state to pick up any Telegram-injected interrupt_queue entries
        from phase3.state_manager import load_state
        fresh = load_state()
        if fresh and fresh.interrupt_queue:
            msg_text = fresh.interrupt_queue[0].strip().lower()
            # Drain the first message
            new_queue = fresh.interrupt_queue[1:]
            from phase3.state_manager import save_state
            save_state(fresh.model_copy(update={"interrupt_queue": new_queue}))

            if msg_text in ("yes", "✅", "approve", "ok", "build", "go"):
                log.info("plan_checkpoint.approved", via="telegram")
                return True
            elif msg_text in ("no", "stop", "cancel"):
                log.info("plan_checkpoint.rejected", via="telegram")
                return True  # still True — caller can check plan_approved on state
            else:
                # Treat as a change instruction — fire replan
                log.info("plan_checkpoint.change_requested", instruction=msg_text)
                change_loops += 1
                try:
                    from agent_y.reasoner import replan
                    from phase3.state_manager import save_state
                    replan_resp = replan(
                        state=state,
                        failed_task=plan[0],
                        failure_type="user_change_request",
                        error_output=msg_text,
                        failed_diff="",
                        thompson_note="",
                    )
                    plan = replan_resp.tasks
                    state = state.model_copy(update={"plan": plan})
                    save_state(state)
                    # Show updated plan
                    updated_msg = format_plan_technical(plan) if user_type == "technical" \
                        else format_plan_general(plan)
                    send(f"✏️ Updated plan:\n{updated_msg}")
                except Exception as exc:
                    log.warning("plan_checkpoint.replan_failed", error=str(exc))
                continue

        time.sleep(5)

    # Timeout — skip optional tasks, auto-approve
    skipped = 0
    for t in plan:
        if not t.required and t.status == "pending":
            t = t.model_copy(update={"status": "skipped"})
            skipped += 1
    if skipped:
        log.info("plan_checkpoint.timeout_skip", skipped=skipped)
        send(f"⏱ No reply — building {len(plan) - skipped} required tasks, skipping {skipped} optional.")
    else:
        log.info("plan_checkpoint.timeout_approve")
        send("⏱ No reply — auto-approving and starting build.")

    return True
