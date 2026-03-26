"""
tests/test_telegram_bot.py
Tests for phase3/telegram_bot.py
"""
import yaml
import pytest
from unittest.mock import MagicMock, patch

from phase3.telegram_bot import _slugify, handle_text, handle_document


class TestSlugify:
    def test_simple_goal(self):
        assert _slugify("build a fastapi backend") == "build_a_fastapi_backend"

    def test_truncates_to_40(self):
        assert len(_slugify("a" * 100)) <= 40

    def test_special_chars_stripped(self):
        assert _slugify("Hello, World!") == "hello_world"

    def test_empty_fallback(self):
        assert _slugify("!!!") == "project"


class TestHandleText:
    def test_creates_yaml_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        with patch("phase3.telegram_bot.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            handle_text("tok", "123", "build a fastapi backend")

        files = list(tmp_path.glob("*.yaml"))
        assert len(files) == 1
        data = yaml.safe_load(files[0].read_text())
        assert data["goal"] == "build a fastapi backend"
        assert "fastapi" in data["project_id"]

    def test_sends_reply(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        with patch("phase3.telegram_bot.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            handle_text("tok", "123", "build something")

        mock_post.assert_called_once()
        assert "123" in str(mock_post.call_args)


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

        assert (tmp_path / "mybrief.yaml").exists()
        assert (tmp_path / "mybrief.yaml").read_bytes() == brief_content
        # No companion YAML created for direct yaml upload
        yamls = list(tmp_path.glob("*.yaml"))
        assert len(yamls) == 1

    def test_pdf_upload_creates_companion_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        with patch("phase3.telegram_bot.requests.get", side_effect=self._mock_get(b"%PDF")):
            with patch("phase3.telegram_bot.requests.post"):
                handle_document("tok", "123", self._make_doc("spec.pdf"))

        assert (tmp_path / "spec.pdf").exists()
        yamls = list(tmp_path.glob("*.yaml"))
        assert len(yamls) == 1
        data = yaml.safe_load(yamls[0].read_text())
        assert "spec.pdf" in data["attachments"]

    def test_unsupported_extension_sends_warning(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phase3.telegram_bot.INTAKE_DIR", tmp_path)
        with patch("phase3.telegram_bot.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            with patch("phase3.telegram_bot.requests.get"):
                handle_document("tok", "123", self._make_doc("image.png"))

        text = mock_post.call_args[1]["json"]["text"]
        assert "Unsupported" in text
        assert not list(tmp_path.glob("*"))

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
