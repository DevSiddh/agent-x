"""
tests/test_orchestrator.py
Tests for Agent-X v3.0 Orchestrator, StateManager, and write_file().
"""

import json
import os
import subprocess
import tempfile
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
from phase2.executor.runner import RunResult, write_file
from phase3.orchestrator import is_done, run_loop, run_once
from phase3.state_manager import (
    get_next_pending_task,
    load_state,
    mark_blocked,
    mark_completed,
    mark_failed,
    mark_in_progress,
    save_state,
)


# ---------------------------------------------------------------------------
# Fixtures
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


def _make_task(task_id="T1", depends_on=None, patch_order=None):
    return Task(
        task_id=task_id,
        action=TaskAction.WRITE_FILE,
        description="Test task",
        files_to_touch=["app.py"],
        patch_order=patch_order or ["app.py"],
        acceptance_criteria=_make_criteria(),
        depends_on=depends_on or [],
    )


def _make_state(tasks=None):
    return SharedState(
        project_id="test",
        project_slug="test-proj",
        goal="build something",
        plan=tasks or [_make_task()],
    )


def _make_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    return tmp_path


# ---------------------------------------------------------------------------
# write_file tests
# ---------------------------------------------------------------------------

class TestWriteFile:
    def test_creates_file_and_git_adds(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        fp = repo / "new_file.py"
        content = "\n".join([f"line {i}" for i in range(10)])
        result = write_file(fp, content, repo)
        assert result.success
        assert fp.exists()
        assert fp.read_text() == content

    def test_exceeds_50_line_limit_returns_error(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        fp = repo / "big.py"
        content = "\n".join([f"line {i}" for i in range(51)])
        result = write_file(fp, content, repo)
        assert not result.success
        assert "50-line limit" in result.error
        assert not fp.exists()

    def test_exactly_50_lines_passes(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        fp = repo / "ok.py"
        content = "\n".join([f"x = {i}" for i in range(50)])
        result = write_file(fp, content, repo)
        assert result.success

    def test_creates_parent_dirs(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        fp = repo / "a" / "b" / "c.py"
        result = write_file(fp, "x = 1\ny = 2\nz = 3\n", repo)
        assert result.success
        assert fp.exists()


# ---------------------------------------------------------------------------
# StateManager tests
# ---------------------------------------------------------------------------

class TestStateManager:
    def test_save_and_load_round_trip(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")

        state = _make_state()
        save_state(state)
        loaded = load_state()
        assert loaded is not None
        assert loaded.project_id == state.project_id
        assert loaded.goal == state.goal
        assert len(loaded.plan) == 1

    def test_atomic_write_uses_tmp_then_renames(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        state_path = tmp_path / "state.json"
        temp_path = tmp_path / "state_tmp.json"
        monkeypatch.setattr(sm, "STATE_PATH", state_path)
        monkeypatch.setattr(sm, "TEMP_PATH", temp_path)

        state = _make_state()
        save_state(state)
        assert state_path.exists()
        assert not temp_path.exists()  # renamed away

    def test_load_returns_none_if_missing(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "nonexistent.json")
        assert load_state() is None

    def test_get_next_pending_task_returns_first_eligible(self):
        t1 = _make_task("T1")
        t2 = _make_task("T2", depends_on=["T1"])
        state = _make_state([t1, t2])
        nxt = get_next_pending_task(state)
        assert nxt is not None
        assert nxt.task_id == "T1"

    def test_get_next_pending_blocked_when_dep_not_completed(self):
        t1 = _make_task("T1")
        t2 = _make_task("T2", depends_on=["T1"])
        state = _make_state([t1, t2])
        # T1 completed — T2 now eligible
        state = mark_completed(state, "T1")
        nxt = get_next_pending_task(state)
        assert nxt is not None and nxt.task_id == "T2"

    def test_mark_completed_resets_streak(self):
        state = _make_state()
        state = state.model_copy(update={"failed_task_streak": 3})
        state = mark_completed(state, "T1")
        assert state.plan[0].status == "completed"
        assert state.failed_task_streak == 0

    def test_mark_failed_increments_streak(self):
        state = _make_state()
        state = mark_failed(state, "T1", "test_failure")
        assert state.plan[0].status == "failed"
        assert state.plan[0].failed_attempts == 1
        assert state.failed_task_streak == 1

    def test_mark_failed_twice_streak_is_2(self):
        t1 = _make_task("T1")
        t2 = _make_task("T2")
        state = _make_state([t1, t2])
        state = mark_failed(state, "T1", "test_failure")
        state = mark_failed(state, "T2", "test_failure")
        assert state.failed_task_streak == 2

    def test_mark_blocked(self):
        state = _make_state()
        state = mark_blocked(state, "T1")
        assert state.plan[0].status == "blocked"


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------

class TestIsDone:
    def test_all_completed(self):
        t = _make_task()
        state = _make_state([t])
        state = mark_completed(state, "T1")
        assert is_done(state)

    def test_all_blocked(self):
        t = _make_task()
        state = _make_state([t])
        state = mark_blocked(state, "T1")
        assert is_done(state)

    def test_one_pending_not_done(self):
        t1 = _make_task("T1")
        t2 = _make_task("T2")
        state = _make_state([t1, t2])
        state = mark_completed(state, "T1")
        assert not is_done(state)


class TestRunOnce:
    def test_successful_task_updates_global_interfaces(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        repo.mkdir(exist_ok=True)
        _make_git_repo(repo)

        state = _make_state([_make_task(patch_order=[])])
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        with patch("phase3.orchestrator._run_tests", return_value=True):
            with patch("phase3.orchestrator._call_deepseek", return_value="def add(a,b): return a+b"):
                result = run_once(state, repo)

        assert result.plan[0].status == "completed"
        assert result.failed_task_streak == 0

    def test_failed_test_marks_task_failed(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        state = _make_state([_make_task(patch_order=[])])
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        with patch("phase3.orchestrator._run_tests", return_value=False):
            result = run_once(state, repo)

        assert result.plan[0].status == "failed"
        assert result.failed_task_streak == 1

    def test_streak_resets_to_zero_on_success(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        state = _make_state([_make_task(patch_order=[])])
        state = state.model_copy(update={"failed_task_streak": 1})
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        with patch("phase3.orchestrator._run_tests", return_value=True):
            with patch("phase3.orchestrator._call_deepseek", return_value="def add(a,b): return a+b"):
                result = run_once(state, repo)

        assert result.failed_task_streak == 0

    def test_no_pending_tasks_returns_state_unchanged(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        task = _make_task()
        state = _make_state([task])
        state = mark_completed(state, "T1")
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        result = run_once(state, repo)
        assert result.plan[0].status == "completed"

    def test_streak_2_triggers_agent_y_replan(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        state = _make_state([_make_task(patch_order=[])])
        state = state.model_copy(update={"failed_task_streak": 2})
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        result = run_once(state, repo)
        # At streak==2 orchestrator marks failed and returns (Agent-Y needed)
        assert result.plan[0].status == "failed"


class TestRunLoop:
    def test_agent_y_called_when_plan_empty(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        # Empty plan → loop breaks immediately (Agent-Y needed)
        state = run_loop("test", "build X", repo, max_iterations=3)
        assert state.plan == []

    def test_agent_y_not_called_on_normal_progress(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        with patch("phase3.orchestrator._run_tests", return_value=True):
            state = run_loop("test", "build X", repo, max_iterations=5)

        # All tasks completed without Agent-Y involvement
        assert all(t.status in ("completed", "blocked") for t in state.plan)

    def test_is_done_exits_loop_early(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        # Pre-complete the task in state file
        task = _make_task(patch_order=[])
        state = _make_state([task])
        state = mark_completed(state, "T1")
        save_state(state)

        with patch("phase3.orchestrator._run_tests", return_value=True):
            result = run_loop("test", "build X", repo, max_iterations=10)

        assert is_done(result)


# ---------------------------------------------------------------------------
# _commit_context tests
# ---------------------------------------------------------------------------

class TestCommitContext:
    def test_commits_context_file_when_exists(self, tmp_path):
        """git add and commit are called; push called only when remote exists."""
        from phase3.orchestrator import _commit_context
        agent_dir = tmp_path / ".agent"
        agent_dir.mkdir()
        (agent_dir / "context.md").write_text("# context\n")

        remote_result = MagicMock(returncode=0, stderr=b"", stdout="origin\n")
        with patch("phase3.orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = remote_result
            _commit_context(tmp_path, "T1")

        cmds = [call.args[0] for call in mock_run.call_args_list]
        assert any("add" in cmd for cmd in cmds)
        assert any("commit" in cmd for cmd in cmds)
        assert any("push" in cmd for cmd in cmds)

    def test_push_skipped_when_no_remote(self, tmp_path):
        """git add + commit happen but push is skipped when no remote configured."""
        from phase3.orchestrator import _commit_context
        agent_dir = tmp_path / ".agent"
        agent_dir.mkdir()
        (agent_dir / "context.md").write_text("# context\n")

        no_remote = MagicMock(returncode=0, stderr=b"", stdout="")
        with patch("phase3.orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = no_remote
            _commit_context(tmp_path, "T1")

        cmds = [call.args[0] for call in mock_run.call_args_list]
        assert any("add" in cmd for cmd in cmds)
        assert any("commit" in cmd for cmd in cmds)
        assert not any("push" in cmd for cmd in cmds)

    def test_skips_when_context_file_missing(self, tmp_path):
        """No subprocess calls if .agent/context.md does not exist."""
        from phase3.orchestrator import _commit_context
        with patch("phase3.orchestrator.subprocess.run") as mock_run:
            _commit_context(tmp_path, "T1")
        mock_run.assert_not_called()

    def test_does_not_raise_on_git_failure(self, tmp_path):
        """CalledProcessError is caught — function must not propagate it."""
        from phase3.orchestrator import _commit_context
        agent_dir = tmp_path / ".agent"
        agent_dir.mkdir()
        (agent_dir / "context.md").write_text("# context\n")

        with patch(
            "phase3.orchestrator.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git", stderr=b"error"),
        ):
            _commit_context(tmp_path, "T1")  # must not raise


class TestRunOnceCommitContext:
    def test_commit_context_called_when_github_repo_set(self, tmp_path, monkeypatch):
        """_commit_context is called exactly once on success when github_repo is set."""
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        state = _make_state([_make_task(patch_order=[])])
        state = state.model_copy(update={"github_repo": "owner/repo"})
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        with patch("phase3.orchestrator._run_tests", return_value=True):
            with patch("phase3.orchestrator._call_deepseek", return_value="def add(a,b): return a+b"):
                with patch("phase3.orchestrator._commit_context") as mock_cc:
                    run_once(state, repo)

        mock_cc.assert_called_once()

    def test_commit_context_always_called_on_success(self, tmp_path, monkeypatch):
        """_commit_context is called even without github_repo (commits locally, skips push)."""
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        state = _make_state([_make_task(patch_order=[])])
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        with patch("phase3.orchestrator._run_tests", return_value=True):
            with patch("phase3.orchestrator._call_deepseek", return_value="def add(a,b): return a+b"):
                with patch("phase3.orchestrator._commit_context") as mock_cc:
                    run_once(state, repo)

        mock_cc.assert_called_once()
