"""
tests/test_skill_vault.py
Tests for SkillVault, retrospective.generate_skill, and Best-of-N orchestrator.
"""

import json
import subprocess
import tempfile
import os
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
from phase2.skills.vault import SkillEntry, SkillVault


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vault(tmp_path: Path) -> SkillVault:
    vault = SkillVault()
    vault.VAULT_PATH = tmp_path / "skill_vault.jsonl"
    vault.SKILL_STATE_PATH = tmp_path / "skill_state.json"
    from phase2.strategy.thompson import ThompsonSampler
    vault._sampler = ThompsonSampler()
    return vault


def _make_entry(skill_id="test_skill", embedding=None) -> SkillEntry:
    return SkillEntry(
        skill_id=skill_id,
        constraint_text="Always check imports first.",
        domain_tags=["python"],
        embedding=embedding or [],
    )


def _make_state() -> SharedState:
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
        description="Create add", files_to_touch=["app.py"],
        acceptance_criteria=criteria,
    )
    return SharedState(
        project_id="test", project_slug="test-proj",
        goal="build calc", plan=[task],
    )


# ---------------------------------------------------------------------------
# SkillVault tests
# ---------------------------------------------------------------------------

class TestAddSkill:
    def test_persists_to_jsonl(self, tmp_path):
        vault = _make_vault(tmp_path)
        entry = _make_entry()
        vault.add_skill(entry)
        assert vault.VAULT_PATH.exists()
        lines = vault.VAULT_PATH.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["skill_id"] == "test_skill"

    def test_inits_thompson_arm(self, tmp_path):
        vault = _make_vault(tmp_path)
        entry = _make_entry("my_skill")
        vault.add_skill(entry)
        arm = vault._sampler.get_arm("my_skill")
        assert arm["alpha"] >= 1
        assert arm["beta"] >= 1

    def test_never_raises_on_bad_input(self, tmp_path):
        vault = _make_vault(tmp_path)
        # Should not raise even with corrupt entry
        vault.add_skill(SkillEntry(skill_id="", constraint_text=""))


class TestFindRelevant:
    def test_returns_all_when_model_unavailable(self, tmp_path):
        vault = _make_vault(tmp_path)
        for i in range(5):
            vault.add_skill(_make_entry(f"skill_{i}"))
        with patch.object(vault, "_get_embedding", return_value=[]):
            results = vault.find_relevant("any goal", k=10)
        assert len(results) == 5

    def test_cosine_ranking_with_mock_embedding(self, tmp_path):
        vault = _make_vault(tmp_path)
        # skill_a has embedding close to goal, skill_b is far
        e_a = _make_entry("skill_a", embedding=[1.0, 0.0])
        e_b = _make_entry("skill_b", embedding=[0.0, 1.0])
        vault.add_skill(e_a)
        vault.add_skill(e_b)
        with patch.object(vault, "_get_embedding", return_value=[1.0, 0.0]):
            results = vault.find_relevant("goal", k=2)
        assert results[0].skill_id == "skill_a"

    def test_returns_empty_when_vault_empty(self, tmp_path):
        vault = _make_vault(tmp_path)
        results = vault.find_relevant("anything")
        assert results == []


class TestSampleTop:
    def test_below_trust_gate_score_is_0_5(self, tmp_path):
        vault = _make_vault(tmp_path)
        entry = _make_entry("low_trust")
        entry = entry.model_copy(update={"alpha": 1, "beta": 1})  # α+β=2, below gate=7
        vault.add_skill(entry)
        with patch.object(vault._sampler, "sample") as mock_sample:
            results = vault.sample_top([entry])
            # Thompson NOT called — below gate
            mock_sample.assert_not_called()
        assert len(results) == 1

    def test_above_trust_gate_uses_thompson(self, tmp_path):
        vault = _make_vault(tmp_path)
        entry = _make_entry("high_trust")
        entry = entry.model_copy(update={"alpha": 4, "beta": 4})  # α+β=8 >= gate=7
        vault.add_skill(entry)
        with patch.object(vault._sampler, "sample", return_value=0.9) as mock_sample:
            results = vault.sample_top([entry])
            mock_sample.assert_called_once_with("high_trust")
        assert results[0].skill_id == "high_trust"

    def test_returns_top_n(self, tmp_path):
        vault = _make_vault(tmp_path)
        skills = [_make_entry(f"s{i}") for i in range(5)]
        results = vault.sample_top(skills, n=3)
        assert len(results) == 3


class TestUpdate:
    def test_win_increments_alpha(self, tmp_path):
        vault = _make_vault(tmp_path)
        vault.add_skill(_make_entry("win_skill"))
        before = vault._sampler.get_arm("win_skill")["alpha"]
        vault.update(["win_skill"], won=True)
        after = vault._sampler.get_arm("win_skill")["alpha"]
        assert after == before + 1

    def test_loss_increments_beta(self, tmp_path):
        vault = _make_vault(tmp_path)
        vault.add_skill(_make_entry("loss_skill"))
        before = vault._sampler.get_arm("loss_skill")["beta"]
        vault.update(["loss_skill"], won=False)
        after = vault._sampler.get_arm("loss_skill")["beta"]
        assert after == before + 1

    def test_never_raises(self, tmp_path):
        vault = _make_vault(tmp_path)
        vault.update(["nonexistent_skill"], won=True)  # should not raise


class TestGetContextBlock:
    def test_empty_vault_returns_empty_string(self, tmp_path):
        vault = _make_vault(tmp_path)
        result = vault.get_context_block("any goal")
        assert result == ""

    def test_nonempty_vault_contains_skill_id(self, tmp_path):
        vault = _make_vault(tmp_path)
        vault.add_skill(_make_entry("my_skill"))
        with patch.object(vault, "_get_embedding", return_value=[]):
            result = vault.get_context_block("some goal")
        assert "my_skill" in result

    def test_never_raises(self, tmp_path):
        vault = _make_vault(tmp_path)
        with patch.object(vault, "find_relevant", side_effect=Exception("boom")):
            result = vault.get_context_block("goal")
        assert result == ""


# ---------------------------------------------------------------------------
# Retrospective tests
# ---------------------------------------------------------------------------

class TestGenerateSkill:
    def test_valid_llm_response_returns_skill_entry(self):
        from agent_y.retrospective import generate_skill
        state = _make_state()
        task = state.plan[0]
        task = task.model_copy(update={"failed_attempts": 2, "status": "completed"})

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "skill_id": "avoid_mutable_defaults",
            "constraint_text": "Never use mutable default arguments.",
            "domain_tags": ["python"],
        })

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key"}):
            with patch("agent_y.retrospective.OpenAI") as MockClient:
                MockClient.return_value.chat.completions.create.return_value = mock_response
                result = generate_skill(state, task, ["diff1"], "winning_diff")

        assert result is not None
        assert result.skill_id == "avoid_mutable_defaults"

    def test_invalid_json_returns_none(self):
        from agent_y.retrospective import generate_skill
        state = _make_state()
        task = state.plan[0]

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "not json at all"

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key"}):
            with patch("agent_y.retrospective.OpenAI") as MockClient:
                MockClient.return_value.chat.completions.create.return_value = mock_response
                result = generate_skill(state, task, ["diff1"], "winning")

        assert result is None

    def test_missing_api_key_returns_none(self):
        from agent_y.retrospective import generate_skill
        state = _make_state()
        task = state.plan[0]
        env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = generate_skill(state, task, ["diff"], "win")
        assert result is None

    def test_empty_diffs_returns_none(self):
        from agent_y.retrospective import generate_skill
        state = _make_state()
        task = state.plan[0]
        result = generate_skill(state, task, [], "")
        assert result is None


# ---------------------------------------------------------------------------
# Best-of-N orchestrator tests
# ---------------------------------------------------------------------------

def _make_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    return tmp_path


class TestBestOfN:
    def _make_state_with_task(self, patch_order=None):
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
            description="build add", files_to_touch=["app.py"],
            patch_order=patch_order or [],
            acceptance_criteria=criteria,
        )
        return SharedState(
            project_id="p", project_slug="proj",
            goal="calc", plan=[task],
        )

    def test_variation_1_passes_stop_immediately(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        state = self._make_state_with_task()
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        call_count = {"n": 0}
        def mock_tests(repo_path, task):
            call_count["n"] += 1
            return True  # pass on first attempt

        from phase3 import orchestrator as orch
        with patch.object(orch, "_run_tests", side_effect=mock_tests):
            result = orch.run_once(state, repo)

        assert result.plan[0].status == "completed"
        assert call_count["n"] == 1  # stopped after first pass

    def test_variation_1_fails_variation_2_tried(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        state = self._make_state_with_task()
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        call_count = {"n": 0}
        def mock_tests(repo_path, task):
            call_count["n"] += 1
            return call_count["n"] >= 2  # fail first, pass second

        from phase3 import orchestrator as orch
        with patch.object(orch, "_run_tests", side_effect=mock_tests):
            result = orch.run_once(state, repo)

        assert result.plan[0].status == "completed"
        assert call_count["n"] == 2

    def test_all_variations_fail_marks_failed(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
        state = self._make_state_with_task()
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        from phase3 import orchestrator as orch
        with patch.object(orch, "_run_tests", return_value=False):
            result = orch.run_once(state, repo)

        assert result.plan[0].status == "failed"

    def test_retrospective_fires_on_failed_attempts_gte_2(self, tmp_path, monkeypatch):
        import phase3.state_manager as sm
        import phase3.project_context as pc
        monkeypatch.setattr(sm, "STATE_PATH", tmp_path / "state.json")
        monkeypatch.setattr(sm, "TEMP_PATH", tmp_path / "state_tmp.json")
        monkeypatch.setattr(pc, "REGISTRY_PATH", tmp_path / "registry.jsonl")

        repo = _make_git_repo(tmp_path / "repo")
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
            description="build add", files_to_touch=["app.py"],
            patch_order=[], acceptance_criteria=criteria,
            failed_attempts=2,  # already struggled
        )
        state = SharedState(
            project_id="p", project_slug="proj", goal="calc", plan=[task],
        )
        os.environ["WORKSPACE_ROOT"] = str(tmp_path)

        from phase3 import orchestrator as orch
        retro_called = {"called": False}

        def mock_generate(*args, **kwargs):
            retro_called["called"] = True
            return None

        with patch.object(orch, "_run_tests", return_value=True):
            with patch("phase3.orchestrator.generate_skill", mock_generate):
                orch.run_once(state, repo)

        assert retro_called["called"]
