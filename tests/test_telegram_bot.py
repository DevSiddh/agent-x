"""
tests/test_telegram_bot.py
Tests for phase3/telegram_bot.py
"""
import json
import yaml
import pytest
from unittest.mock import MagicMock, patch

from phase3.telegram_bot import (
    _slugify,
    apply_universal_template,
    get_blocked_project,
    handle_text,
    handle_document,
    start_new_project,
    resume_project,
    _save_pending_spec,
    _load_pending_spec,
    _clear_pending_spec,
)


class TestSlugify:
    def test_simple_goal(self):
        assert _slugify("build a fastapi backend") == "build_a_fastapi_backend"

    def test_truncates_to_40(self):
        assert len(_slugify("a" * 100)) <= 40

    def test_special_chars_stripped(self):
        assert _slugify("Hello, World!") == "hello_world"

    def test_empty_fallback(self):
        assert _slugify("!!!") == "project"


class TestUniversalTemplate:
    def test_contains_original_goal(self):
        out = apply_universal_template("build a fastapi backend")
        assert "build a fastapi backend" in out

    def test_contains_test_first_requirement(self):
        out = apply_universal_template("anything")
        assert "tests first" in out

    def test_contains_flat_structure_requirement(self):
        out = apply_universal_template("anything")
        assert "Flat file" in out


class TestGetBlockedProject:
    def test_returns_none_when_no_registry(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.REGISTRY_PATH", tmp_path / "none.jsonl")
        assert get_blocked_project() is None

    def test_returns_none_when_no_blocked(self, tmp_path, monkeypatch):
        reg = tmp_path / "registry.jsonl"
        reg.write_text(json.dumps({"project_slug": "p1", "status": "completed"}) + "\n")
        monkeypatch.setattr("phase3.telegram_bot.REGISTRY_PATH", reg)
        assert get_blocked_project() is None

    def test_returns_blocked_project(self, tmp_path, monkeypatch):
        reg = tmp_path / "registry.jsonl"
        entry = {"project_slug": "my_proj", "status": "blocked_waiting_for_user"}
        reg.write_text(json.dumps(entry) + "\n")
        monkeypatch.setattr("phase3.telegram_bot.REGISTRY_PATH", reg)
        result = get_blocked_project()
        assert result is not None
        assert result["project_slug"] == "my_proj"


class TestPendingSpec:
    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.PENDING_SPEC_PATH", tmp_path / "pending.json")
        _save_pending_spec("build a bot", "build_a_bot")
        result = _load_pending_spec()
        assert result == {"goal": "build a bot", "project_id": "build_a_bot"}

    def test_load_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.PENDING_SPEC_PATH", tmp_path / "none.json")
        assert _load_pending_spec() is None

    def test_clear_removes_file(self, tmp_path, monkeypatch):
        path = tmp_path / "pending.json"
        path.write_text("{}")
        monkeypatch.setattr("phase3.telegram_bot.PENDING_SPEC_PATH", path)
        _clear_pending_spec()
        assert not path.exists()


class TestHandleText:
    def test_new_project_asks_spec_questions(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        monkeypatch.setattr("phase3.telegram_bot.REGISTRY_PATH", tmp_path / "empty.jsonl")
        monkeypatch.setattr("phase3.telegram_bot.PENDING_SPEC_PATH", tmp_path / "p.json")
        with patch("phase3.telegram_bot.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            handle_text("tok", "123", "build a fastapi backend")

        # No YAML yet — waiting for spec reply
        assert not list(tmp_path.glob("*.yaml"))
        text = mock_post.call_args[1]["json"]["text"]
        assert "specs needed" in text

    def test_new_project_saves_pending_spec(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        monkeypatch.setattr("phase3.telegram_bot.REGISTRY_PATH", tmp_path / "empty.jsonl")
        pending_path = tmp_path / "pending.json"
        monkeypatch.setattr("phase3.telegram_bot.PENDING_SPEC_PATH", pending_path)
        with patch("phase3.telegram_bot.requests.post"):
            handle_text("tok", "123", "build a fastapi backend")
        assert pending_path.exists()
        data = json.loads(pending_path.read_text())
        assert data["goal"] == "build a fastapi backend"

    def test_routes_to_resume_when_blocked_exists(self, tmp_path, monkeypatch):
        reg = tmp_path / "registry.jsonl"
        reg.write_text(json.dumps({
            "project_slug": "my_proj", "status": "blocked_waiting_for_user"
        }) + "\n")
        monkeypatch.setattr("phase3.telegram_bot.REGISTRY_PATH", reg)

        with patch("phase3.telegram_bot.resume_project") as mock_resume:
            handle_text("tok", "123", "sqlite please")

        mock_resume.assert_called_once_with("tok", "123", "my_proj", "sqlite please")


class TestResumeProject:
    def test_spec_reply_creates_brief_yaml(self, tmp_path, monkeypatch):
        """When pending spec exists, reply combines goal+specs → creates brief.yaml."""
        pending_path = tmp_path / "pending.json"
        pending_path.write_text(json.dumps({"goal": "build a bot", "project_id": "build_a_bot"}))
        monkeypatch.setattr("phase3.telegram_bot.PENDING_SPEC_PATH", pending_path)
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)

        with patch("phase3.telegram_bot.requests.post"):
            resume_project("tok", "123", "build_a_bot", "separate project, sqlite")

        files = list(tmp_path.glob("*.yaml"))
        assert len(files) == 1
        data = yaml.safe_load(files[0].read_text())
        assert "build a bot" in data["goal"]
        assert "sqlite" in data["goal"]
        assert "tests first" in data["goal"]  # universal template applied
        assert not pending_path.exists()  # cleared after use

    def test_spec_reply_sends_confirmation(self, tmp_path, monkeypatch):
        pending_path = tmp_path / "pending.json"
        pending_path.write_text(json.dumps({"goal": "build a bot", "project_id": "build_a_bot"}))
        monkeypatch.setattr("phase3.telegram_bot.PENDING_SPEC_PATH", pending_path)
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)

        with patch("phase3.telegram_bot.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            resume_project("tok", "123", "build_a_bot", "separate, sqlite")

        text = mock_post.call_args[1]["json"]["text"]
        assert "Building" in text or "▶️" in text


class TestHandleDocument:
    def _make_doc(self, name: str) -> dict:
        return {"file_name": name, "file_id": "abc123"}

    def _mock_get(self, content: bytes = b"data"):
        file_resp = MagicMock()
        file_resp.json.return_value = {"result": {"file_path": "docs/file.yaml"}}
        content_resp = MagicMock()
        content_resp.content = content
        return [file_resp, content_resp]

    def test_yaml_upload_dropped_directly(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        brief_content = b"project_id: test\ngoal: hello\n"
        with patch("phase3.telegram_bot.requests.get", side_effect=self._mock_get(brief_content)):
            with patch("phase3.telegram_bot.requests.post"):
                handle_document("tok", "123", self._make_doc("mybrief.yaml"))

        assert (tmp_path / "mybrief.yaml").read_bytes() == brief_content

    def test_pdf_upload_creates_companion_yaml_with_template(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        with patch("phase3.telegram_bot.requests.get", side_effect=self._mock_get(b"%PDF")):
            with patch("phase3.telegram_bot.requests.post"):
                handle_document("tok", "123", self._make_doc("spec.pdf"))

        assert (tmp_path / "spec.pdf").exists()
        yamls = list(tmp_path.glob("*.yaml"))
        assert len(yamls) == 1
        data = yaml.safe_load(yamls[0].read_text())
        assert "spec.pdf" in data["attachments"]
        assert "tests first" in data["goal"]  # template applied

    def test_unsupported_extension_sends_warning(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        with patch("phase3.telegram_bot.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            with patch("phase3.telegram_bot.requests.get"):
                handle_document("tok", "123", self._make_doc("image.png"))

        text = mock_post.call_args[1]["json"]["text"]
        assert "Unsupported" in text

    def test_missing_file_path_sends_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        bad_resp = MagicMock()
        bad_resp.json.return_value = {"result": {}}
        with patch("phase3.telegram_bot.requests.get", return_value=bad_resp):
            with patch("phase3.telegram_bot.requests.post") as mock_post:
                mock_post.return_value = MagicMock(status_code=200)
                handle_document("tok", "123", self._make_doc("brief.yaml"))

        text = mock_post.call_args[1]["json"]["text"]
        assert "❌" in text
