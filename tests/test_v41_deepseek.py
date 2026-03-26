"""
tests/test_v41_deepseek.py
Tests for v4.1 — DeepSeek wiring in Orchestrator.
_build_agent_x_prompt, _call_deepseek, _execute_file_ops, plan_goal integration.
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_y.schemas import (
    AcceptanceCase,
    AcceptanceCriteria,
    SharedState,
    Task,
    TaskAction,
)
from phase3.orchestrator import (
    AGENT_X_STATIC_PROMPT,
    _build_agent_x_prompt,
    _call_deepseek,
    _execute_file_ops,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_criteria(fn="add"):
    return AcceptanceCriteria(
        target_function=fn,
        cases=[
            AcceptanceCase(inputs=["add(1,2)"], expected="3"),
            AcceptanceCase(inputs=["add(0,0)"], expected="0"),
            AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
        ],
    )


def _make_task(patch_order=None, hint=""):
    return Task(
        task_id="T1", action=TaskAction.WRITE_FILE,
        description="Create add function",
        files_to_touch=["src/add.py"],
        patch_order=patch_order or ["src/add.py"],
        acceptance_criteria=_make_criteria(),
        hint=hint,
    )


def _make_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    return tmp_path


# ---------------------------------------------------------------------------
# _build_agent_x_prompt tests
# ---------------------------------------------------------------------------

class TestBuildAgentXPrompt:
    def test_contains_task_description(self):
        task = _make_task()
        prompt = _build_agent_x_prompt(task, "src/add.py", TaskAction.WRITE_FILE)
        assert "Create add function" in prompt

    def test_contains_target_function(self):
        task = _make_task()
        prompt = _build_agent_x_prompt(task, "src/add.py", TaskAction.WRITE_FILE)
        assert "add" in prompt

    def test_contains_acceptance_cases(self):
        task = _make_task()
        prompt = _build_agent_x_prompt(task, "src/add.py", TaskAction.WRITE_FILE)
        assert "add(1,2)" in prompt
        assert "3" in prompt

    def test_contains_hint_when_set(self):
        task = _make_task(hint="Use integer addition only")
        prompt = _build_agent_x_prompt(task, "src/add.py", TaskAction.WRITE_FILE)
        assert "Use integer addition only" in prompt

    def test_no_hint_section_when_empty(self):
        task = _make_task(hint="")
        prompt = _build_agent_x_prompt(task, "src/add.py", TaskAction.WRITE_FILE)
        assert "Hint:" not in prompt

    def test_write_file_says_create(self):
        task = _make_task()
        prompt = _build_agent_x_prompt(task, "src/add.py", TaskAction.WRITE_FILE)
        assert "Create" in prompt

    def test_file_edit_says_edit(self):
        task = _make_task()
        prompt = _build_agent_x_prompt(task, "src/add.py", TaskAction.FILE_EDIT)
        assert "Edit" in prompt


# ---------------------------------------------------------------------------
# _call_deepseek tests
# ---------------------------------------------------------------------------

class TestCallDeepseek:
    def test_returns_content_on_success(self):
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "def add(a, b):\n    return a + b\n"
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key"}):
            with patch("phase3.orchestrator.OpenAI") as MockClient:
                MockClient.return_value.chat.completions.create.return_value = mock_resp
                result = _call_deepseek("build add function")
        assert "def add" in result

    def test_returns_empty_on_no_api_key(self):
        env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = _call_deepseek("build add")
        assert result == ""

    def test_returns_empty_on_api_error(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key"}):
            with patch("phase3.orchestrator.OpenAI") as MockClient:
                MockClient.return_value.chat.completions.create.side_effect = Exception("timeout")
                result = _call_deepseek("build add")
        assert result == ""

    def test_never_raises(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "bad_key"}):
            with patch("phase3.orchestrator.OpenAI", side_effect=Exception("import error")):
                result = _call_deepseek("anything")
        assert result == ""


# ---------------------------------------------------------------------------
# _execute_file_ops tests
# ---------------------------------------------------------------------------

class TestExecuteFileOps:
    def test_calls_deepseek_and_writes_file(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        task = _make_task(patch_order=["src/add.py"])
        fake_content = "def add(a, b):\n    return a + b\n"

        with patch("phase3.orchestrator._call_deepseek", return_value=fake_content):
            result = _execute_file_ops(task, repo)

        assert result is True
        assert (repo / "src" / "add.py").exists()
        assert "def add" in (repo / "src" / "add.py").read_text()

    def test_returns_false_on_empty_deepseek_response(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        task = _make_task(patch_order=["src/add.py"])

        with patch("phase3.orchestrator._call_deepseek", return_value=""):
            result = _execute_file_ops(task, repo)

        assert result is False

    def test_injects_hint_into_prompt(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        task = _make_task(patch_order=["src/add.py"], hint="Use integers only")
        prompts_seen = []

        def capture_prompt(prompt):
            prompts_seen.append(prompt)
            return "def add(a, b):\n    return a + b\n"

        with patch("phase3.orchestrator._call_deepseek", side_effect=capture_prompt):
            _execute_file_ops(task, repo)

        assert any("Use integers only" in p for p in prompts_seen)

    def test_empty_patch_order_returns_true(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        task = _make_task(patch_order=["src/add.py"])
        fake_content = "def add(a, b):\n    return a + b\n"
        with patch("phase3.orchestrator._call_deepseek", return_value=fake_content):
            result = _execute_file_ops(task, repo)
        assert result is True


# ---------------------------------------------------------------------------
# run_loop Agent-Y integration tests
# ---------------------------------------------------------------------------

class TestRunLoopAgentY:
    def _make_state(self, tmp_path):
        return SharedState(
            project_id="test", project_slug="test-proj",
            goal="build add function", plan=[],
        )

    def test_plan_goal_called_when_plan_empty(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        plan_called = {"n": 0}
        mock_tasks = [_make_task(patch_order=[])]

        def mock_plan_goal(goal, state):
            plan_called["n"] += 1
            return mock_tasks

        from phase3 import orchestrator as orch
        import phase3.orchestrator as _orch_mod
        _orch_mod.plan_goal = mock_plan_goal
        try:
            with patch.object(orch, "_run_tests", return_value=True):
                orch.run_loop("test", "build add", repo, max_iterations=5)
        finally:
            from agent_y.reasoner import plan_goal as _orig
            _orch_mod.plan_goal = _orig

        assert plan_called["n"] >= 1

    def test_plan_goal_not_called_when_plan_exists(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        # Pre-save state with a plan
        state = SharedState(
            project_id="test", project_slug=repo.name,
            goal="build add", plan=[_make_task(patch_order=[])],
        )
        from phase3.state_manager import save_state
        save_state(state)

        plan_called = {"n": 0}

        from phase3 import orchestrator as orch
        with patch("phase3.orchestrator.plan_goal", lambda **kw: plan_called.update(n=plan_called["n"]+1) or []):
            with patch.object(orch, "_run_tests", return_value=True):
                orch.run_loop("test", "build add", repo, max_iterations=3)

        assert plan_called["n"] == 0
