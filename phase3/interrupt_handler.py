"""
phase3/interrupt_handler.py
FIX-12 — Mid-task interrupt handler.

Three functions:
  parse_intent(message)         → dict  {action: STOP|SKIP|MODIFY|CONTINUE, ...}
  cascade_skip(state, keyword)  → SharedState  (marks tasks + dependents SKIPPED)
  check_interrupts(state)       → dict  (drains queue, returns highest-priority intent)

Architecture advantage: atomic 50-line tasks create a natural interrupt window
between every task. This is free — no polling overhead, no threads.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agent_y.schemas import SharedState

log = structlog.get_logger()

# Intent priority (highest wins when multiple messages queued)
_PRIORITY = {"STOP": 4, "SKIP": 3, "MODIFY": 2, "CONTINUE": 1}

_STOP_PATTERNS = [
    r"\bstop\b", r"\bhalt\b", r"\babort\b", r"\bcancel\b", r"\bkill\b",
]
_SKIP_PATTERNS = [
    r"\bskip\s+(.+)",
    r"(.+?)\s+already\s+exists?",
    r"don['\u2019]?t\s+build\s+(.+)",
    r"ignore\s+(.+)",
    r"remove\s+(.+)",
]
_MODIFY_PATTERNS = [
    r"\bchange\s+(.+?)\s+to\s+(.+)",
    r"\buse\s+(.+?)\s+instead",
    r"\bswitch\s+to\s+(.+)",
]


def parse_intent(message: str) -> dict:
    """
    Parse a plain-text Telegram message into a structured intent.

    Returns one of:
      {action: "STOP"}
      {action: "SKIP",   keyword: str}
      {action: "MODIFY", instruction: str}
      {action: "CONTINUE"}
    """
    text = message.strip().lower()

    # STOP
    for pat in _STOP_PATTERNS:
        if re.search(pat, text):
            return {"action": "STOP"}

    # SKIP — extract keyword
    for pat in _SKIP_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            keyword = m.group(1).strip().rstrip(".,!?")
            return {"action": "SKIP", "keyword": keyword}

    # MODIFY — pass full instruction
    for pat in _MODIFY_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return {"action": "MODIFY", "instruction": message.strip()}

    return {"action": "CONTINUE"}


def cascade_skip(state: "SharedState", keyword: str) -> "SharedState":
    """
    Mark all tasks matching keyword as SKIPPED.
    Then cascade: any task that depends_on a SKIPPED task → also SKIPPED.
    Returns updated state (does NOT save — caller must save_state).
    """
    skipped_ids: set[str] = set()
    new_plan = []

    # Pass 1 — direct keyword match on pending tasks
    for t in state.plan:
        if t.status == "pending" and keyword.lower() in t.description.lower():
            new_plan.append(t.model_copy(update={"status": "skipped"}))
            skipped_ids.add(t.task_id)
            log.info("interrupt.cascade_skip.direct",
                     task_id=t.task_id, description=t.description[:50], keyword=keyword)
        else:
            new_plan.append(t)

    # Pass 2 — cascade to dependents (repeat until stable)
    changed = True
    while changed:
        changed = False
        for i, t in enumerate(new_plan):
            if t.status == "pending" and set(t.depends_on) & skipped_ids:
                new_plan[i] = t.model_copy(update={"status": "skipped"})
                skipped_ids.add(t.task_id)
                log.info("interrupt.cascade_skip.dependent",
                         task_id=t.task_id, depends_on=t.depends_on)
                changed = True

    return state.model_copy(update={"plan": new_plan})


def check_interrupts(state: "SharedState") -> dict:
    """
    Drain state.interrupt_queue. Return highest-priority intent found.
    Removes processed messages from queue — caller must save updated state.

    Returns (intent_dict, updated_state) as a tuple.
    """
    if not state.interrupt_queue:
        return {"action": "CONTINUE"}, state

    intents = []
    for msg in state.interrupt_queue:
        intents.append(parse_intent(msg))

    # Clear the queue — messages consumed
    state = state.model_copy(update={"interrupt_queue": []})

    # Return highest priority intent
    best = max(intents, key=lambda i: _PRIORITY.get(i["action"], 1))
    log.info("interrupt.check", found=len(intents), best=best["action"])
    return best, state
