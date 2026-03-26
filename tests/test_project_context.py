"""
tests/test_project_context.py
Tests for v3.1 — project context + registry.
"""

import json
import subprocess
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_y.schemas import (
    AcceptanceCase,
    AcceptanceCriteria,
    SharedState,
    Task,
    TaskAction,
)
from phase3.project_context import (
    CONTEXT_FILE,
    append_task,
    read_context,
    register_project,
    scaffold_context,
    update_registry_last_task,
    REGISTRY_PATH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(slug="test-proj"):
    criteria = AcceptanceCriteria(
        target_function="add",
        cases=[
            AcceptanceCase(inputs=["add(1,2)"], expected="3"),
            AcceptanceCase(inputs=["add(0,0)"], expected="0"),
            AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
        ],
    )
    task = Task(
        task_id="T1", action=TaskAction.WRITE_FILE,
        description="Create add function",
        files_to_touch=["src/add.py"],
        acceptance_criteria=criteria,
    )
    return SharedState(
        project_id="test", project_slug=slug,
        goal="Build a calculator", plan=[task],
    )


def _make_task(task_id="T1", files=None):
    criteria = AcceptanceCriteria(
        target_function="add",
        cases=[
            AcceptanceCase(inputs=["add(1,2)"], expected="3"),
            AcceptanceCase(inputs=["add(0,0)"], expected="0"),
            AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
        ],
    )
    return Task(
        task_id=task_id, action=TaskAction.WRITE_FILE,
        description=f"Task {task_id}", files_to_touch=files or ["src/add.py"],
        acceptance_criteria=criteria,
    )


# ---------------------------------------------------------------------------
# scaffold_context tests
# ---------------------------------------------------------------------------

class TestScaffoldContext:
    def test_creates_context_file(self, tmp_path):
        state = _make_state()
        scaffold_context(state, tmp_path)
        assert (tmp_path / CONTEXT_FILE).exists()

    def test_contains_goal(self, tmp_path):
        state = _make_state()
        scaffold_context(state, tmp_path)
        content = (tmp_path / CONTEXT_FILE).read_text()
        assert "Build a calculator" in content

    def test_creates_parent_dirs(self, tmp_path):
        state = _make_state()
        repo = tmp_path / "deep" / "nested"
        scaffold_context(state, repo)
        assert (repo / CONTEXT_FILE).exists()

    def test_never_raises_on_bad_path(self):
        state = _make_state()
        # read-only path — should not raise
        scaffold_context(state, Path("/nonexistent/readonly/path"))


# ---------------------------------------------------------------------------
# append_task tests
# ---------------------------------------------------------------------------

class TestAppendTask:
    def test_appends_task_id(self, tmp_path):
        state = _make_state()
        scaffold_context(state, tmp_path)
        task = _make_task("T1")
        append_task(state, task, tmp_path)
        content = read_context(tmp_path)
        assert "T1" in content

    def test_appends_file_to_key_files(self, tmp_path):
        state = _make_state()
        scaffold_context(state, tmp_path)
        task = _make_task("T1", files=["src/add.py"])
        append_task(state, task, tmp_path)
        content = read_context(tmp_path)
        assert "src/add.py" in content

    def test_scaffolds_if_context_missing(self, tmp_path):
        state = _make_state()
        task = _make_task("T1")
        # No scaffold called first
        append_task(state, task, tmp_path)
        assert (tmp_path / CONTEXT_FILE).exists()

    def test_last_task_updated_on_second_call(self, tmp_path):
        state = _make_state()
        scaffold_context(state, tmp_path)
        append_task(state, _make_task("T1"), tmp_path)
        append_task(state, _make_task("T2"), tmp_path)
        content = read_context(tmp_path)
        assert "T2" in content

    def test_never_raises(self, tmp_path):
        state = _make_state()
        append_task(state, _make_task("T1"), Path("/nonexistent"))


# ---------------------------------------------------------------------------
# read_context tests
# ---------------------------------------------------------------------------

class TestReadContext:
    def test_returns_empty_if_missing(self, tmp_path):
        result = read_context(tmp_path)
        assert result == ""

    def test_returns_content_if_exists(self, tmp_path):
        state = _make_state()
        scaffold_context(state, tmp_path)
        result = read_context(tmp_path)
        assert "Goal" in result

    def test_never_raises(self):
        result = read_context(Path("/nonexistent"))
        assert result == ""


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_registers_project(self, tmp_path, monkeypatch):
        import phase3.project_context as pc
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        state = _make_state("my-proj")
        register_project(state)
        assert (tmp_path / "registry.jsonl").exists()
        lines = (tmp_path / "registry.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["project_slug"] == "my-proj"
        assert entry["goal"] == "Build a calculator"

    def test_idempotent_no_duplicate(self, tmp_path, monkeypatch):
        import phase3.project_context as pc
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        state = _make_state("my-proj")
        register_project(state)
        register_project(state)  # second call — should not duplicate
        lines = (tmp_path / "registry.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1

    def test_update_last_task(self, tmp_path, monkeypatch):
        import phase3.project_context as pc
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        state = _make_state("my-proj")
        register_project(state)
        update_registry_last_task("my-proj", "T5")
        entry = json.loads(
            (tmp_path / "registry.jsonl").read_text().strip().splitlines()[0]
        )
        assert entry["last_task"] == "T5"

    def test_update_nonexistent_does_not_raise(self, tmp_path, monkeypatch):
        import phase3.project_context as pc
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")
        update_registry_last_task("ghost-proj", "T1")  # should not raise

    def test_multiple_projects(self, tmp_path, monkeypatch):
        import phase3.project_context as pc
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        register_project(_make_state("proj-a"))
        register_project(_make_state("proj-b"))
        lines = (tmp_path / "registry.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# Orchestrator integration — context written after task completes
# ---------------------------------------------------------------------------

class TestOrchestratorContextWire:
    def _make_git_repo(self, tmp_path):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
        return tmp_path

    def test_context_file_written_after_task_completes(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = self._make_git_repo(tmp_path / "repo")
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        criteria = AcceptanceCriteria(
            target_function="add",
            cases=[
                AcceptanceCase(inputs=["add(1,2)"], expected="3"),
                AcceptanceCase(inputs=["add(0,0)"], expected="0"),
                AcceptanceCase(inputs=["add(-1,1)"], expected="0"),
            ],
        )
        task = Task(
            task_id="T1", action=TaskAction.WRITE_FILE,
            description="build add", files_to_touch=["src/add.py"],
            patch_order=[], acceptance_criteria=criteria,
        )
        state = SharedState(
            project_id="p", project_slug="test-proj",
            goal="build calc", plan=[task],
        )

        from phase3 import orchestrator as orch
        with patch.object(orch, "_run_tests", return_value=True):
            orch.run_once(state, repo)

        context = read_context(repo)
        assert "T1" in context

    def test_registry_entry_created_on_run_loop(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = self._make_git_repo(tmp_path / "repo")
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        from phase3 import orchestrator as orch
        with patch.object(orch, "_run_tests", return_value=True):
            orch.run_loop("test", "build calc", repo, max_iterations=2)

        assert (tmp_path / "registry.jsonl").exists()
