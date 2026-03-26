"""
tests/test_reasoner_creation.py
Tests for Agent-Y v3.0 creation mode: plan_goal(), replan(), and schema validation.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from agent_y.schemas import (
    AcceptanceCase,
    AcceptanceCriteria,
    ReplanAnalysis,
    ReplanResponse,
    SharedState,
    Task,
    TaskAction,
)
from agent_y.reasoner import ReasonerError, plan_goal, replan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cases(n: int) -> list[dict]:
    return [{"inputs": [f"add({i},{i})"], "expected": str(i * 2)} for i in range(n)]


def _make_task_dict(task_id: str = "T1", files_count: int = 1, cases_count: int = 3) -> dict:
    return {
        "task_id": task_id,
        "action": "write_file",
        "description": f"Create function for {task_id}",
        "files_to_touch": [f"file{i}.py" for i in range(files_count)],
        "acceptance_criteria": {
            "target_function": "add",
            "cases": _make_cases(cases_count),
        },
    }


def _mock_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_shared_state() -> SharedState:
    criteria = AcceptanceCriteria(
        target_function="add",
        cases=[
            AcceptanceCase(inputs=["add(1,2)"], expected="3"),
            AcceptanceCase(inputs=["add(0,0)"], expected="0"),
            AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
        ],
    )
    task = Task(
        task_id="T1",
        action=TaskAction.WRITE_FILE,
        description="Create add function",
        files_to_touch=["app.py"],
        acceptance_criteria=criteria,
    )
    return SharedState(
        project_id="proj-1",
        project_slug="my-project",
        goal="Build a calculator",
        plan=[task],
    )


@pytest.fixture
def state() -> SharedState:
    return _make_shared_state()


# ---------------------------------------------------------------------------
# plan_goal tests
# ---------------------------------------------------------------------------


class TestPlanGoal:
    def test_valid_response_returns_tasks(self, state: SharedState) -> None:
        payload = json.dumps({"tasks": [_make_task_dict("T1"), _make_task_dict("T2")]})
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(payload)

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client), patch.dict(
            "os.environ", {"DEEPSEEK_API_KEY": "test-key"}
        ):
            result = plan_goal("Build a calculator", state)

        assert len(result) == 2
        assert all(isinstance(t, Task) for t in result)
        assert result[0].task_id == "T1"
        assert result[1].task_id == "T2"

    def test_files_to_touch_max_exceeded_raises(self, state: SharedState) -> None:
        bad = _make_task_dict("T1", files_count=4)  # 4 > max 3
        payload = json.dumps({"tasks": [bad]})
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(payload)

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client), patch.dict(
            "os.environ", {"DEEPSEEK_API_KEY": "test-key"}
        ):
            with pytest.raises(ReasonerError):
                plan_goal("Build something", state)

    def test_too_few_acceptance_cases_raises(self, state: SharedState) -> None:
        bad = _make_task_dict("T1", cases_count=2)  # 2 < min 3
        payload = json.dumps({"tasks": [bad]})
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(payload)

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client), patch.dict(
            "os.environ", {"DEEPSEEK_API_KEY": "test-key"}
        ):
            with pytest.raises(ReasonerError):
                plan_goal("Build something", state)

    def test_bad_json_retries_and_succeeds(self, state: SharedState) -> None:
        good = json.dumps({"tasks": [_make_task_dict("T1")]})
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _mock_response("not valid json {{{"),
            _mock_response(good),
        ]

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client), patch.dict(
            "os.environ", {"DEEPSEEK_API_KEY": "test-key"}
        ):
            result = plan_goal("Build a calculator", state)

        assert len(result) == 1
        assert mock_client.chat.completions.create.call_count == 2

    def test_bad_json_twice_raises_reasoner_error(self, state: SharedState) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            "not valid json {{{"
        )

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client), patch.dict(
            "os.environ", {"DEEPSEEK_API_KEY": "test-key"}
        ):
            with pytest.raises(ReasonerError, match="plan_goal failed after 2 attempts"):
                plan_goal("Build a calculator", state)

        assert mock_client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# replan tests
# ---------------------------------------------------------------------------


class TestReplan:
    def _valid_replan_payload(self) -> str:
        return json.dumps(
            {
                "analysis": {
                    "root_cause_of_failure": "wrong algorithm used",
                    "flaw_in_previous_approach": "used string concat instead of int add",
                    "explicit_pivot_strategy": "use int() cast before addition",
                },
                "new_sub_tasks": [_make_task_dict("T1a"), _make_task_dict("T1b")],
            }
        )

    def test_all_seven_context_fields_injected(self, state: SharedState) -> None:
        failed_task = state.plan[0]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            self._valid_replan_payload()
        )

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client), patch.dict(
            "os.environ", {"DEEPSEEK_API_KEY": "test-key"}
        ):
            replan(
                state=state,
                failed_task=failed_task,
                failure_type="test_failure",
                error_output="AssertionError: expected 3 got '3'\nTraceback...",
                failed_diff="--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x=1\n+x='1'",
                thompson_note="test_failure in RuntimeError solved 60% by type cast",
            )

        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]

        assert failed_task.description in user_msg          # field 1
        assert "test_failure" in user_msg                   # field 2
        assert "AssertionError" in user_msg                 # field 3
        assert "app.py" in user_msg                         # field 4 (files_to_touch)
        assert "add(1,2)" in user_msg                       # field 5 (acceptance cases)
        assert "--- a/app.py" in user_msg                   # field 6 (failed_diff)
        assert "test_failure in RuntimeError" in user_msg   # field 7 (thompson_note)

    def test_missing_root_cause_raises_reasoner_error(self, state: SharedState) -> None:
        bad = json.dumps(
            {
                "analysis": {
                    "root_cause_of_failure": "",  # empty — should fail
                    "flaw_in_previous_approach": "used string",
                    "explicit_pivot_strategy": "use int cast",
                },
                "new_sub_tasks": [_make_task_dict("T1a")],
            }
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(bad)

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client), patch.dict(
            "os.environ", {"DEEPSEEK_API_KEY": "test-key"}
        ):
            with pytest.raises(ReasonerError):
                replan(
                    state=state,
                    failed_task=state.plan[0],
                    failure_type="test_failure",
                    error_output="some error",
                    failed_diff="some diff",
                    thompson_note="some note",
                )

    def test_new_sub_tasks_replaces_only_failed_not_full_plan(
        self, state: SharedState
    ) -> None:
        """Verify new_sub_tasks is 2 replacement tasks, not the full original plan."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_response(
            self._valid_replan_payload()
        )

        with patch("agent_y.reasoner.OpenAI", return_value=mock_client), patch.dict(
            "os.environ", {"DEEPSEEK_API_KEY": "test-key"}
        ):
            result = replan(
                state=state,
                failed_task=state.plan[0],
                failure_type="test_failure",
                error_output="error",
                failed_diff="diff",
                thompson_note="note",
            )

        # 2 surgical sub-tasks (T1a + T1b), not the full original 1-task plan
        assert len(result.new_sub_tasks) == 2
        assert result.new_sub_tasks[0].task_id == "T1a"
        assert result.new_sub_tasks[1].task_id == "T1b"
        assert isinstance(result, ReplanResponse)


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_shared_state_failed_task_streak_default_zero(self) -> None:
        state = _make_shared_state()
        assert state.failed_task_streak == 0

    def test_shared_state_streak_updates(self) -> None:
        state = _make_shared_state()
        updated = state.model_copy(update={"failed_task_streak": 2})
        assert updated.failed_task_streak == 2
        assert state.failed_task_streak == 0  # original unchanged

    def test_acceptance_criteria_min_length_enforced(self) -> None:
        with pytest.raises(ValidationError):
            AcceptanceCriteria(
                target_function="add",
                cases=[
                    AcceptanceCase(inputs=["1"], expected="1"),
                    AcceptanceCase(inputs=["2"], expected="2"),
                ],
            )

    def test_acceptance_criteria_exactly_three_passes(self) -> None:
        criteria = AcceptanceCriteria(
            target_function="add",
            cases=[
                AcceptanceCase(inputs=["a"], expected="b"),
                AcceptanceCase(inputs=["c"], expected="d"),
                AcceptanceCase(inputs=["e"], expected="f"),
            ],
        )
        assert len(criteria.cases) == 3

    def test_acceptance_case_coerces_int_inputs_to_str(self) -> None:
        """DeepSeek returns numeric inputs as ints — schema must coerce to str."""
        case = AcceptanceCase(inputs=[2, 3], expected=5)  # type: ignore[arg-type]
        assert case.inputs == ["2", "3"]
        assert case.expected == "5"

    def test_acceptance_case_coerces_mixed_inputs(self) -> None:
        """Mixed int/str inputs all coerced to str."""
        case = AcceptanceCase(inputs=[1, "two", 3.0], expected=0)  # type: ignore[arg-type]
        assert case.inputs == ["1", "two", "3.0"]
        assert case.expected == "0"

    def test_acceptance_case_pure_str_inputs_unchanged(self) -> None:
        """String inputs pass through without change."""
        case = AcceptanceCase(inputs=["add(1,2)"], expected="3")
        assert case.inputs == ["add(1,2)"]
        assert case.expected == "3"

    def test_task_status_transitions(self) -> None:
        task = Task(
            task_id="T1",
            action=TaskAction.WRITE_FILE,
            description="Create function",
            files_to_touch=["app.py"],
            acceptance_criteria=AcceptanceCriteria(
                target_function="foo",
                cases=[
                    AcceptanceCase(inputs=["a"], expected="b"),
                    AcceptanceCase(inputs=["c"], expected="d"),
                    AcceptanceCase(inputs=["e"], expected="f"),
                ],
            ),
        )
        assert task.status == "pending"

        in_progress = task.model_copy(update={"status": "in_progress"})
        assert in_progress.status == "in_progress"

        completed = in_progress.model_copy(update={"status": "completed"})
        assert completed.status == "completed"
