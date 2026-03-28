"""
agent_y/schemas.py
Pydantic v2 models for Agent-X v3.0 shared state and planning.
Standalone — no imports from phase1/ phase2/ phase3/.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AcceptanceCase(BaseModel):
    """One I/O test case for a task's acceptance criteria."""

    inputs: list[str]
    expected: str

    @field_validator("inputs", mode="before")
    @classmethod
    def coerce_inputs_to_str(cls, v: list) -> list[str]:
        return [str(i) for i in v]

    @field_validator("expected", mode="before")
    @classmethod
    def coerce_expected_to_str(cls, v: object) -> str:
        return str(v)


class AcceptanceCriteria(BaseModel):
    """Anti-reward-hacking gate: min 3 I/O pairs — Happy Path + Edge Case + Error Case.
    Exception: scaffold and requirements tasks use cases=[] (no tests for stubs/deps).
    """

    target_function: str
    cases: list[AcceptanceCase] = Field(min_length=0)  # Task validator enforces min=3 for impl tasks


class ArtifactEntry(BaseModel):
    """Tracks a file written by the pipeline with checksum for tamper detection."""

    file: str
    last_modified_task: str
    checksum: str  # sha256 — verified before each task; halt if changed outside pipeline


class TaskAction(str, Enum):
    """Valid actions a task can perform."""

    SCAFFOLD = "scaffold"
    WRITE_FILE = "write_file"
    FILE_EDIT = "file_edit"
    RUN_TESTS = "run_tests"


class Task(BaseModel):
    """One atomic unit of work in the execution plan."""

    task_id: str
    action: TaskAction
    description: str
    files_to_touch: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_files_limit(self) -> "Task":
        if len(self.files_to_touch) > 3:
            raise ValueError(f"files_to_touch max 3, got {len(self.files_to_touch)}")
        return self

    @model_validator(mode="after")
    def check_acceptance_criteria(self) -> "Task":
        """Scaffold and requirements tasks have no cases. All others need min 3."""
        exempt = {TaskAction.SCAFFOLD}
        is_requirements = (
            self.action == TaskAction.WRITE_FILE
            and self.acceptance_criteria.target_function == "requirements"
        )
        if self.action not in exempt and not is_requirements:
            if len(self.acceptance_criteria.cases) < 3:
                raise ValueError(
                    f"Task {self.task_id}: acceptance_criteria needs min 3 cases, "
                    f"got {len(self.acceptance_criteria.cases)}"
                )
        return self
    patch_order: list[str] = []
    acceptance_criteria: AcceptanceCriteria
    depends_on: list[str] = []
    status: Literal["pending", "in_progress", "completed", "failed", "blocked", "skipped"] = "pending"
    failed_attempts: int = 0
    variations_tried: int = 0  # Best-of-N: how many variants attempted before pass
    hint: str = ""  # optional constraint injected into Agent-X prompt
    required: bool = True  # FIX-11: False = optional, skipped on timeout


class SharedState(BaseModel):
    """Single source of truth for the orchestrator loop."""

    project_id: str
    project_slug: str  # e.g. "crypto-bot-v1" — WORKSPACE_ROOT resolves full path
    goal: str
    plan: list[Task]
    current_task_id: str | None = None
    failed_task_streak: int = 0
    last_failed_diff: str = ""   # FIX-6: last DeepSeek output that failed — passed to replan()
    global_interfaces: dict[str, list[str]] = {}
    artifacts: list[ArtifactEntry] = []
    github_repo: str = ""      # e.g. "DevSiddh/agent-x" — for PR comments
    pr_number: int | None = None  # set after PR is opened
    # FIX-11: plan checkpoint
    plan_approved: bool = False
    interrupt_queue: list[str] = []  # FIX-12: pending Telegram messages between tasks


class ReplanAnalysis(BaseModel):
    """Forced root-cause analysis before any new sub-tasks are written."""

    root_cause_of_failure: str
    flaw_in_previous_approach: str
    explicit_pivot_strategy: str


class ReplanResponse(BaseModel):
    """Surgical sub-tasking: failed task replaced by 2+ sub-tasks, never full rewrite."""

    analysis: ReplanAnalysis
    new_sub_tasks: list[Task]


def resolve_safe_path(relative: str) -> Path:
    """
    Resolve a relative path within WORKSPACE_ROOT.
    Raises PermissionError on path traversal (sandbox escape blocked).
    """
    root = Path(os.environ["WORKSPACE_ROOT"]).resolve()
    full = (root / relative).resolve()
    if not str(full).startswith(str(root)):
        raise PermissionError(f"Sandbox escape blocked: {relative}")
    return full


if __name__ == "__main__":
    # Smoke test: instantiate each model
    _criteria = AcceptanceCriteria(
        target_function="add",
        cases=[
            AcceptanceCase(inputs=["add(1, 2)"], expected="3"),
            AcceptanceCase(inputs=["add(0, 0)"], expected="0"),
            AcceptanceCase(inputs=["add(-1, 1)"], expected="0"),
        ],
    )
    _task = Task(
        task_id="T1",
        action=TaskAction.WRITE_FILE,
        description="Create add function",
        files_to_touch=["app.py"],
        acceptance_criteria=_criteria,
    )
    _state = SharedState(
        project_id="proj-1",
        project_slug="my-project",
        goal="Build a calculator",
        plan=[_task],
    )
    _analysis = ReplanAnalysis(
        root_cause_of_failure="Wrong algorithm",
        flaw_in_previous_approach="Used string concat instead of int add",
        explicit_pivot_strategy="Use int() cast before addition",
    )
    _replan = ReplanResponse(analysis=_analysis, new_sub_tasks=[_task])
    _artifact = ArtifactEntry(file="app.py", last_modified_task="T1", checksum="abc123")

    print("=== schemas.py Smoke Test ===")
    print(f"Task:          {_task.task_id} — {_task.action} — status: {_task.status}")
    print(f"SharedState:   {_state.project_id} — goal: {_state.goal}")
    print(f"ReplanResponse: {len(_replan.new_sub_tasks)} sub-task(s)")
    print(f"ArtifactEntry: {_artifact.file} checksum={_artifact.checksum}")
    print("PASSED")
