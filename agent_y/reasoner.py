"""
agent_y/reasoner.py
Reasoning layer for Agent-X. Slots between ContextBuilder and DeepSeekWorker.
Decides HOW to fix before DeepSeekWorker generates the patch.
Does NOT generate code or patches — reasoning and strategy only.
"""

import json
from typing import Literal

import structlog
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

from agent_y.schemas import ReplanResponse, SharedState, Task
from phase2.classifier.regex_pass import ClassifierResult

log = structlog.get_logger()

MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Category → keyword mapping for strategy validation (P1)
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "DependencyError": ["dependency", "package", "install", "requirements", "setuptools", "module"],
    "EnvironmentError": ["env", "build", "config", "environment", "variable", "flag", "isolation", "pycache", "cache", "process"],
    "ConfigError": ["import", "config", "missing", "module", "table", "migration", "schema", "yaml"],
    "RuntimeError": ["schema", "type", "model", "namespace", "conflict", "field", "pydantic"],
    "NetworkError": ["connection", "retry", "timeout", "network", "port", "socket"],
    "BuildError": ["docker", "build", "image", "isolation"],
}

_SYSTEM_PROMPT = """You are a reasoning engine for a CI/CD self-healing system.
Your job is to analyze a build failure and decide the best fix strategy.

Return ONLY valid JSON. No markdown. No fences. No explanation outside the JSON.
Start your response with { and end with }.

Required JSON schema (all fields mandatory):
{
  "action": "repair" | "observe" | "escalate",
  "reasoning": "why this strategy was selected (1-2 sentences)",
  "strategy": "concrete fix approach — specific to the error, not generic",
  "confidence": 0.0 to 1.0,
  "files_to_change": ["list", "of", "file", "paths"] (max 3 files),
  "diagnosis": "one sentence: what is broken and why (plain English, no jargon)"
}

Rules:
- action must be exactly one of: repair, observe, escalate
- strategy must be specific to the error type — not generic advice
- files_to_change must only include files mentioned in the error context (max 3)
- confidence is your internal estimate — float between 0.0 and 1.0
- diagnosis must be plain English, max 200 chars, no code snippets
- Do NOT generate code or patches — reasoning and strategy only"""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ReasonerOutput(BaseModel):
    action: Literal["repair", "observe", "escalate", "plan", "next_task", "replan"]
    reasoning: str
    strategy: str
    confidence: float = Field(ge=0.0, le=1.0)
    files_to_change: list[str]
    diagnosis: str = ""  # 1 sentence: what is broken and why (plain English)

    @field_validator("files_to_change")
    @classmethod
    def cap_files(cls, v: list[str]) -> list[str]:
        if len(v) > 3:
            raise ValueError(f"files_to_change has {len(v)} items — max is 3")
        return v

    @field_validator("strategy")
    @classmethod
    def strategy_non_empty(cls, v: str) -> str:
        if not v or len(v.strip()) < 5:
            raise ValueError("strategy must be a non-empty, meaningful string")
        return v

    @field_validator("diagnosis")
    @classmethod
    def diagnosis_max_length(cls, v: str) -> str:
        if len(v) > 200:
            return v[:200]
        return v


class ReasonerError(Exception):
    """Raised when Reasoner exhausts retries or cannot produce valid output."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_json(raw: str) -> dict:
    """Strip markdown fences and parse the first JSON object found."""
    cleaned = raw.strip()
    for fence in ("```json", "```JSON", "```"):
        if cleaned.startswith(fence):
            cleaned = cleaned[len(fence):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    start = cleaned.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", cleaned, 0)
    return json.loads(cleaned[start:])


def validate_strategy(strategy: str, category: str) -> bool:
    """
    Check that strategy is semantically related to the classified error category.
    Prevents valid JSON with wrong strategy from passing silently (P1).
    """
    keywords = _CATEGORY_KEYWORDS.get(category, [])
    return any(kw in strategy.lower() for kw in keywords)


def _filter_files(
    files: list[str], context: str, affected_file: str
) -> list[str]:
    """
    Keep only files mentioned in the context or matching the affected file.
    Hard cap at 3 to prevent wide hallucinated edits (P4).
    """
    allowed = [f for f in files if f in context or f == affected_file]
    if not allowed and files:
        # Fallback: keep affected_file if no overlap found
        allowed = [affected_file]
    return allowed[:3]


def _build_user_prompt(
    context: str, category: str, attempt: int, error_msg: str = ""
) -> str:
    if attempt == 0:
        return (
            f"{context}\n\n"
            f"What is the best fix strategy for this {category}? "
            f"Return ONLY the JSON object — no explanation outside it."
        )
    return (
        f"{context}\n\n"
        f"Previous attempt FAILED. Reason: {error_msg}\n\n"
        f"Required keys: action, reasoning, strategy, confidence, files_to_change\n"
        f"action must be one of: repair, observe, escalate\n"
        f"Return ONLY the JSON object starting with {{. No markdown. No fences."
    )


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def reason(context: str, classification: ClassifierResult) -> ReasonerOutput:
    """
    Reason about the best fix strategy for the classified error.

    Args:
        context:        Enriched context string from build_context().
        classification: ClassifierResult from regex classifier.

    Returns:
        ReasonerOutput with action, reasoning, strategy, confidence, files_to_change.

    Raises:
        ReasonerError: after MAX_RETRIES exhausted or strategy validation fails.
    """
    import os

    def _get_api_key() -> str:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise EnvironmentError("DEEPSEEK_API_KEY not set")
        return key

    client = OpenAI(api_key=_get_api_key(), base_url="https://api.deepseek.com")

    category = classification.category
    affected_file = classification.affected_file
    last_error = ""

    for attempt in range(MAX_RETRIES + 1):
        user_prompt = _build_user_prompt(context, category, attempt, last_error)

        try:
            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=300,
            )
            raw = response.choices[0].message.content or ""

            parsed = _extract_json(raw)

            # Validate all required keys present
            required = {"action", "reasoning", "strategy", "confidence", "files_to_change", "diagnosis"}
            missing = required - set(parsed.keys())
            if missing:
                raise KeyError(f"Missing keys: {missing}")

            # Validate strategy relates to error category (P1)
            strategy = parsed["strategy"]
            if not validate_strategy(strategy, category):
                raise ValueError(
                    f"strategy '{strategy[:60]}...' does not match category '{category}'"
                )

            # Filter files to only context-relevant ones, cap at 3 (P4)
            files = _filter_files(
                parsed.get("files_to_change", []), context, affected_file
            )

            output = ReasonerOutput(
                action=parsed["action"],
                reasoning=parsed["reasoning"],
                strategy=strategy,
                confidence=float(parsed["confidence"]),
                files_to_change=files,
                diagnosis=str(parsed.get("diagnosis", "")),
            )

            # confidence logged as metadata only — never used in decisions (P3)
            log.info(
                "reasoner.ok",
                category=category,
                action=output.action,
                strategy=output.strategy[:80],
                confidence=output.confidence,
                files=output.files_to_change,
                attempt=attempt,
            )
            return output

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = str(exc)
            log.warning(
                "reasoner.retry",
                attempt=attempt,
                max_retries=MAX_RETRIES,
                error=last_error,
                category=category,
            )

    raise ReasonerError(
        f"Reasoner exhausted {MAX_RETRIES} retries for category={category}. "
        f"Last error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Creation mode — prompts + functions
# ---------------------------------------------------------------------------

CREATION_SYSTEM_PROMPT = """You are a planning engine for an autonomous software engineer.

SCAFFOLD RULE (mandatory — no exceptions):
- ALWAYS emit T0 first with action="scaffold"
- T0 lists ALL files the project will ever touch in files_to_touch (every .py file)
- T0 has NO acceptance_criteria — use: {"target_function": "scaffold", "cases": []}
- T0 has NO depends_on
- After T0: emit tasks in TOPOLOGICAL ORDER (files with no imports first, files that import others last)
  Example order: models.py → schemas.py → routes.py (routes imports both)
- T0 guarantees every stub exists before any task runs — eliminates all ImportError on missing files

Break a goal into 2-4 tasks MAX (after T0). Each task must:
- Touch EXACTLY 2 files: one test file (test_*.py) and one implementation file
- NEVER create a task with 3 or more files
- ALWAYS include BOTH the test file AND the implementation file in the same task
- Have exactly 3 acceptance criteria cases: a Happy Path case, an Edge Case, and an Error Case
- Be atomic and independently testable
- ALWAYS put test file (test_<name>.py) FIRST in patch_order, implementation file SECOND
- Use FLAT file structure — all files in project root, no src/ or tests/ subdirectories
- Test file imports: use module name only, e.g. "from add import add" not "from src.add import add"
- All inputs and expected values in acceptance criteria MUST be strings
- target_function MUST be the implementation function name (e.g. "create_todo_table"), NEVER a test function name (never "test_*")
- CRITICAL: inputs must be a single function call on ONE line: ["add(1, 2)"] not multi-step code
- CRITICAL: expected must be the EXACT Python return value as string: "3", "[]", "None", '{"id":1}'
- NEVER use expected="success" or expected="created" — only actual return values
- NEVER use multi-step inputs like ["conn = get_db()", "conn.cursor()"] — one call only
- Implementation files must RETURN the expected value from the target function
- For APIs: define a plain function (NOT FastAPI route) named after the target_function. FastAPI routes are tested via httpx TestClient separately.
- For FastAPI tests: test files MUST use "from fastapi.testclient import TestClient; from <module> import app; client = TestClient(app)" and call client.get/post/put/delete
- For databases: use sqlite3 (stdlib) — do NOT use sqlalchemy
- For database tests: ALWAYS use in-memory DB (sqlite3.connect(":memory:")) in a pytest fixture with setup/teardown. Never use a file-based DB in tests.
- Available packages: fastapi, flask, httpx, pytest, pydantic. Use ONLY these + stdlib
- target_function for FastAPI tasks: name it after the route function (e.g. "get_todos" for GET /todos)
- Each file must be ≤ 150 lines
- Group related functionality: all CRUD operations for one resource = ONE task, not 5

REQUIREMENTS RULE (mandatory — no exceptions):
- ALWAYS emit T1 with action="write_file" to create requirements.txt
- T1 comes immediately after T0 scaffold, before any implementation task
- T1 files_to_touch: ["requirements.txt"], patch_order: ["requirements.txt"]
- T1 acceptance_criteria: {"target_function": "requirements", "cases": []}
- Infer packages from the goal: FastAPI goal → fastapi, uvicorn, pydantic; Telegram → python-telegram-bot; etc.
- Always include pytest. Always pin nothing — bare package names only (e.g. "fastapi" not "fastapi==0.100.0")
- requirements.txt content: one package per line, stdlib packages NEVER listed
- All implementation tasks depend_on: ["T0", "T1"]

PLAN SIZE RULES (strict):
- Simple project (1 module): 1-2 tasks (+ T0 + T1)
- Medium project (API + DB): 2-3 tasks (+ T0 + T1)
- Complex project (API + DB + auth): 3-4 tasks (+ T0 + T1)
- NEVER create one task per endpoint — group all endpoints for a resource into one task

Output valid JSON only. Start with { and nothing else before it.

EXAMPLE — simple function (T0 scaffold + T1 requirements always first):
{"tasks": [{"task_id": "T0", "action": "scaffold", "description": "Scaffold project files", "files_to_touch": ["add.py", "test_add.py"], "patch_order": [], "acceptance_criteria": {"target_function": "scaffold", "cases": []}, "depends_on": []}, {"task_id": "T1", "action": "write_file", "description": "Create requirements.txt", "files_to_touch": ["requirements.txt"], "patch_order": ["requirements.txt"], "acceptance_criteria": {"target_function": "requirements", "cases": []}, "depends_on": ["T0"]}, {"task_id": "T2", "action": "write_file", "description": "Create add module", "files_to_touch": ["test_add.py", "add.py"], "patch_order": ["test_add.py", "add.py"], "acceptance_criteria": {"target_function": "add", "cases": [{"inputs": ["add(2, 3)"], "expected": "5"}, {"inputs": ["add(0, 0)"], "expected": "0"}, {"inputs": ["add(-1, 1)"], "expected": "0"}]}, "depends_on": ["T0", "T1"]}]}

EXAMPLE — FastAPI with TestClient (target_function must be an HTTP test function name):
{"tasks": [{"task_id": "T1", "action": "write_file", "description": "Create FastAPI todo app", "files_to_touch": ["test_todo_api.py", "todo_api.py"], "patch_order": ["test_todo_api.py", "todo_api.py"], "acceptance_criteria": {"target_function": "test_get_todos", "cases": [{"inputs": ["client.get('/todos').status_code"], "expected": "200"}, {"inputs": ["client.get('/todos').json()"], "expected": "[]"}, {"inputs": ["client.post('/todos', json={'title':'x'}).status_code"], "expected": "201"}]}, "depends_on": []}]}

Required JSON schema (one task shown):
{
  "tasks": [
    {
      "task_id": "T1",
      "action": "write_file",
      "description": "what this task does",
      "files_to_touch": ["test_add.py", "add.py"],
      "patch_order": ["test_add.py", "add.py"],
      "acceptance_criteria": {
        "target_function": "add",
        "cases": [
          {"inputs": ["add(2, 3)"], "expected": "5"},
          {"inputs": ["add(0, 0)"], "expected": "0"},
          {"inputs": ["add(-1, 1)"], "expected": "0"}
        ]
      },
      "depends_on": []
    }
  ]
}"""

REPLAN_SYSTEM_PROMPT = """You are a root-cause analysis engine for a CI/CD self-healing system.
A task has failed. Perform surgical sub-tasking ONLY.
Replace the failed task with 2-3 smaller sub-tasks. Never rewrite the full plan.

Output valid JSON only. Start with { and nothing else before it.

Required JSON schema:
{
  "analysis": {
    "root_cause_of_failure": "specific root cause (non-empty)",
    "flaw_in_previous_approach": "what was wrong about the failed diff (non-empty)",
    "explicit_pivot_strategy": "the new approach (non-empty)"
  },
  "new_sub_tasks": [
    {
      "task_id": "T1a",
      "action": "write_file" | "file_edit" | "run_tests",
      "description": "sub-task description",
      "files_to_touch": ["file.py"],
      "patch_order": ["file.py"],
      "acceptance_criteria": {
        "target_function": "function_name",
        "cases": [
          {"inputs": ["arg1"], "expected": "result"},
          {"inputs": ["edge_input"], "expected": "edge_result"},
          {"inputs": ["error_input"], "expected": "error_result"}
        ]
      },
      "depends_on": []
    }
  ]
}"""


def plan_goal(goal: str, state: SharedState, existing_context: str = "") -> list[Task]:
    """
    Plan a goal into ordered Tasks using deepseek-reasoner.

    Args:
        goal:             The high-level goal to plan.
        state:            Current SharedState (provides project context).
        existing_context: Contents of .agent/context.md — injected on resume so
                          Agent-Y knows what's already built. Empty on first run.

    Returns:
        Parsed list[Task] with validated acceptance criteria (min 3 cases each).

    Raises:
        ReasonerError: After 2 failed attempts (bad JSON or validation failure).
    """
    import os

    def _get_api_key() -> str:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise EnvironmentError("DEEPSEEK_API_KEY not set")
        return key

    client = OpenAI(api_key=_get_api_key(), base_url="https://api.deepseek.com")

    # FIX-5: inject existing context on resume so Agent-Y doesn't restart from scratch
    context_block = (
        f"\n\n## What has already been built\n{existing_context}\n"
        "Continue from where the project left off. Do NOT recreate completed tasks."
    ) if existing_context.strip() else ""

    user_prompt = (
        f"Project: {state.project_slug}\n"
        f"Goal: {goal}"
        f"{context_block}\n\n"
        "Break this goal into ordered tasks. "
        "Return ONLY the JSON object starting with {. No markdown. No explanation."
    )
    last_error = ""

    for attempt in range(2):
        if attempt > 0:
            user_prompt = (
                f"Your output was not valid JSON or failed validation. "
                f"Error: {last_error}\n"
                f"Return only the JSON object starting with {{. Goal: {goal}"
            )
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": CREATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=2000,
                temperature=0.2,
            )
            raw = response.choices[0].message.content or ""
            parsed = _extract_json(raw)
            tasks_data = parsed.get("tasks", [])
            tasks = [Task(**t) for t in tasks_data]  # Pydantic validates each Task

            log.info("reasoner.plan_goal.ok", goal=goal[:60], task_count=len(tasks))
            return tasks

        except Exception as exc:
            last_error = str(exc)
            log.warning(
                "reasoner.plan_goal.retry",
                attempt=attempt,
                error=last_error,
                goal=goal[:60],
            )

    log.error("reasoner.plan_goal.error", goal=goal[:60], error=last_error)
    raise ReasonerError(f"plan_goal failed after 2 attempts. Last error: {last_error}")


def replan(
    state: SharedState,
    failed_task: Task,
    failure_type: str,
    error_output: str,
    failed_diff: str,
    thompson_note: str,
) -> ReplanResponse:
    """
    Surgical replan: replace a failed task with 2-3 sub-tasks.

    Injects all 7 context fields into the prompt (exact order):
    1. Failed task description
    2. failure_type
    3. Error output (last 20 lines)
    4. files_to_touch
    5. Failed acceptance cases
    6. failed_diff
    7. thompson_note

    Returns:
        ReplanResponse with validated non-empty analysis fields and new sub-tasks.

    Raises:
        ReasonerError: On parse failure or empty analysis fields.
    """
    import os

    def _get_api_key() -> str:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise EnvironmentError("DEEPSEEK_API_KEY not set")
        return key

    client = OpenAI(api_key=_get_api_key(), base_url="https://api.deepseek.com")

    error_lines = error_output.strip().splitlines()
    error_snippet = "\n".join(error_lines[-20:])

    failed_cases_text = "\n".join(
        f"  case {i}: inputs={c.inputs} expected={c.expected}"
        for i, c in enumerate(failed_task.acceptance_criteria.cases)
    )

    user_prompt = (
        f"Failed task description: {failed_task.description}\n"
        f"Failure type: {failure_type}\n"
        f"Error output (last 20 lines):\n{error_snippet}\n"
        f"Files to touch: {failed_task.files_to_touch}\n"
        f"Failed acceptance cases:\n{failed_cases_text}\n"
        f"Failed diff:\n{failed_diff}\n"
        f"Thompson note: {thompson_note}\n\n"
        "Return ONLY the JSON object starting with {. No markdown."
    )

    try:
        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": REPLAN_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1000,
        )
        raw = response.choices[0].message.content or ""
        parsed = _extract_json(raw)
        result = ReplanResponse(**parsed)

        # Validate all 3 analysis fields are non-empty
        analysis = result.analysis
        if not analysis.root_cause_of_failure.strip():
            raise ValueError("root_cause_of_failure is empty")
        if not analysis.flaw_in_previous_approach.strip():
            raise ValueError("flaw_in_previous_approach is empty")
        if not analysis.explicit_pivot_strategy.strip():
            raise ValueError("explicit_pivot_strategy is empty")

        log.info(
            "reasoner.replan.ok",
            task_id=failed_task.task_id,
            new_task_count=len(result.new_sub_tasks),
        )
        return result

    except Exception as exc:
        log.error(
            "reasoner.replan.error",
            task_id=failed_task.task_id,
            error=str(exc),
        )
        raise ReasonerError(
            f"replan failed for task {failed_task.task_id}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    from unittest.mock import MagicMock

    mock_response_content = json.dumps({
        "action": "repair",
        "reasoning": "Setuptools is missing from requirements, causing pkg_resources import to fail.",
        "strategy": "Add setuptools to requirements.txt to resolve the missing dependency.",
        "confidence": 0.9,
        "files_to_change": ["requirements.txt"],
    })

    mock_choice = MagicMock()
    mock_choice.message.content = mock_response_content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    cls_result = ClassifierResult(
        category="DependencyError",
        confidence=0.99,
        matched_pattern=r"ModuleNotFoundError",
        keyword="pkg_resources",
        affected_file="requirements.txt",
        bug_signature="smoke/test:DependencyError:pkg_resources:requirements.txt",
    )

    context = (
        "Error Category: DependencyError\n"
        "Affected File: requirements.txt\n"
        "Error Log:\nModuleNotFoundError: No module named 'pkg_resources'"
    )

    # Inject mock by temporarily replacing the module-level OpenAI symbol
    os.environ["DEEPSEEK_API_KEY"] = "test-key"
    _real_OpenAI = globals()["OpenAI"]
    globals()["OpenAI"] = lambda **_kw: mock_client
    try:
        output = reason(context, cls_result)
    finally:
        globals()["OpenAI"] = _real_OpenAI

    print("=== Reasoner Smoke Test ===")
    print(f"action:          {output.action}")
    print(f"strategy:        {output.strategy}")
    print(f"confidence:      {output.confidence}  (metadata only — not used in decisions)")
    print(f"files_to_change: {output.files_to_change}")
    print("PASSED")
