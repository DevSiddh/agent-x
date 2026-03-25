"""
agent_y/retrospective.py
Retrospective skill generation — fires when a task eventually succeeds
after 2+ failed attempts. Abstracts the winning pivot into a reusable skill.
Never raises. All errors → log + return None.
"""

import json
import os
import sys
from pathlib import Path

import structlog
from openai import OpenAI

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent_y.schemas import SharedState, Task
from phase2.skills.vault import SkillEntry

log = structlog.get_logger()

RETRO_SYSTEM_PROMPT = (
    "You are a skill abstraction engine. "
    "Given failed attempts and a winning solution, extract a generalized constraint. "
    "Do NOT include specific variable names or file paths. "
    "Output JSON only: {\"skill_id\": str, \"constraint_text\": str, \"domain_tags\": [str]}. "
    "Start with { and nothing else."
)


def generate_skill(
    state: SharedState,
    failed_task: Task,
    failed_diffs: list[str],
    winning_diff: str,
) -> SkillEntry | None:
    """
    Calls deepseek-reasoner to abstract the winning pivot.
    Returns SkillEntry or None if abstraction fails.
    Never raises.
    structlog: retrospective.ok / retrospective.skip / retrospective.error
    """
    try:
        if not failed_diffs or not winning_diff:
            log.info("retrospective.skip", reason="missing_diffs", task_id=failed_task.task_id)
            return None

        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            log.warning("retrospective.skip", reason="no_api_key")
            return None

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

        failed_summary = "\n---\n".join(
            f"Failed attempt {i+1}:\n{d[:300]}" for i, d in enumerate(failed_diffs)
        )
        user_prompt = (
            f"Task: {failed_task.description}\n\n"
            f"Failed diffs ({len(failed_diffs)}):\n{failed_summary}\n\n"
            f"Winning diff:\n{winning_diff[:500]}\n\n"
            "Abstract the winning pivot into a generalized constraint."
        )

        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": RETRO_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()

        # Extract JSON
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            log.warning("retrospective.error", reason="no_json", task_id=failed_task.task_id)
            return None

        data = json.loads(raw[start:end])
        skill_id = data.get("skill_id", "").strip()
        constraint = data.get("constraint_text", "").strip()
        tags = data.get("domain_tags", [])

        if not skill_id or not constraint:
            log.info("retrospective.skip", reason="empty_fields", task_id=failed_task.task_id)
            return None

        entry = SkillEntry(
            skill_id=skill_id,
            constraint_text=constraint,
            domain_tags=tags if isinstance(tags, list) else [],
            source=f"{state.project_slug}:{failed_task.task_id}",
        )
        log.info("retrospective.ok", skill_id=skill_id, task_id=failed_task.task_id)
        return entry

    except Exception as exc:
        log.error("retrospective.error", error=str(exc), task_id=failed_task.task_id)
        return None
