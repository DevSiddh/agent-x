"""
tests/test_project_manager.py
Tests for phase3/project_manager.py
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from phase3.project_manager import (
    add_github_remote,
    create_github_repo,
    delete_project,
    list_projects,
    _remove_from_registry,
)


class TestCreateGithubRepo:
    def test_returns_none_when_no_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_USERNAME", raising=False)
        assert create_github_repo("my_proj") is None

    def test_returns_clone_url_on_201(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_USERNAME", "devuser")
        mock_resp = MagicMock(status_code=201)
        with patch("phase3.project_manager.requests.post", return_value=mock_resp):
            url = create_github_repo("my_proj")
        assert url == "https://github.com/devuser/my_proj.git"

    def test_returns_clone_url_on_422_already_exists(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_USERNAME", "devuser")
        mock_resp = MagicMock(status_code=422)
        with patch("phase3.project_manager.requests.post", return_value=mock_resp):
            url = create_github_repo("my_proj")
        assert url is not None

    def test_returns_none_on_api_error(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_USERNAME", "devuser")
        with patch("phase3.project_manager.requests.post", side_effect=ConnectionError()):
            url = create_github_repo("my_proj")
        assert url is None


class TestAddGithubRemote:
    def test_adds_remote_when_none_exists(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
        result = add_github_remote(tmp_path, "https://github.com/u/r.git")
        assert result is True

    def test_skips_when_origin_already_set(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/u/r.git"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        result = add_github_remote(tmp_path, "https://github.com/u/r.git")
        assert result is True


class TestListProjects:
    def test_returns_empty_when_no_registry(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.project_manager.REGISTRY_PATH", tmp_path / "none.jsonl")
        assert list_projects() == []

    def test_returns_entries_sorted_by_date(self, tmp_path, monkeypatch):
        reg = tmp_path / "registry.jsonl"
        reg.write_text(
            json.dumps({"project_slug": "a", "status": "completed", "created_at": "2026-03-01"}) + "\n" +
            json.dumps({"project_slug": "b", "status": "active", "created_at": "2026-03-26"}) + "\n"
        )
        monkeypatch.setattr("phase3.project_manager.REGISTRY_PATH", reg)
        entries = list_projects()
        assert entries[0]["project_slug"] == "b"  # newest first


class TestDeleteProject:
    def test_removes_local_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.project_manager.REGISTRY_PATH", tmp_path / "reg.jsonl")
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        project_dir = tmp_path / "my_proj"
        project_dir.mkdir()
        (project_dir / "main.py").write_text("x=1")

        delete_project("my_proj")
        assert not project_dir.exists()

    def test_removes_from_registry(self, tmp_path, monkeypatch):
        reg = tmp_path / "registry.jsonl"
        reg.write_text(
            json.dumps({"project_slug": "my_proj", "status": "failed"}) + "\n" +
            json.dumps({"project_slug": "other", "status": "completed"}) + "\n"
        )
        monkeypatch.setattr("phase3.project_manager.REGISTRY_PATH", reg)
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        delete_project("my_proj")
        remaining = [json.loads(l) for l in reg.read_text().splitlines() if l.strip()]
        assert len(remaining) == 1
        assert remaining[0]["project_slug"] == "other"

    def test_archives_github_by_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.project_manager.REGISTRY_PATH", tmp_path / "reg.jsonl")
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_USERNAME", "user")

        with patch("phase3.project_manager.requests.patch") as mock_patch:
            mock_patch.return_value = MagicMock(status_code=200)
            msg = delete_project("my_proj", archive_github=True)

        call_json = mock_patch.call_args[1]["json"]
        assert call_json.get("archived") is True
        assert "archived" in msg

    def test_hard_delete_calls_delete_endpoint(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.project_manager.REGISTRY_PATH", tmp_path / "reg.jsonl")
        monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_USERNAME", "user")

        with patch("phase3.project_manager.requests.delete") as mock_del:
            mock_del.return_value = MagicMock(status_code=204)
            msg = delete_project("my_proj", archive_github=False)

        mock_del.assert_called_once()
        assert "deleted" in msg
