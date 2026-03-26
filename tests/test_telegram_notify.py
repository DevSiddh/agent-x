"""
tests/test_telegram_notify.py
Tests for phase3/telegram_notify.py
"""
from unittest.mock import MagicMock, patch

import pytest

from phase3.telegram_notify import notify_loop_done, notify_loop_failed, send


class TestSend:
    def test_sends_message_on_success(self, monkeypatch):
        """POST is called with correct URL and payload when env vars are set."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        mock_resp = MagicMock(status_code=200)
        with patch("phase3.telegram_notify.requests.post", return_value=mock_resp) as mock_post:
            send("hello")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["chat_id"] == "12345"
        assert call_kwargs["json"]["text"] == "hello"

    def test_skips_when_token_missing(self, monkeypatch):
        """No HTTP call when TELEGRAM_BOT_TOKEN is not set."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

        with patch("phase3.telegram_notify.requests.post") as mock_post:
            send("hello")  # must not raise

        mock_post.assert_not_called()

    def test_does_not_raise_on_network_error(self, monkeypatch):
        """ConnectionError is caught — send() must not propagate it."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        with patch("phase3.telegram_notify.requests.post", side_effect=ConnectionError("timeout")):
            send("hello")  # must not raise


class TestNotifyLoopDone:
    def test_done_message_format(self, monkeypatch):
        """Completed-only run sends ✅ DONE message."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

        with patch("phase3.telegram_notify.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            notify_loop_done("my_proj", completed=3, failed=0, blocked=0)

        text = mock_post.call_args[1]["json"]["text"]
        assert "✅ DONE" in text
        assert "my_proj" in text

    def test_partial_message_when_failures(self, monkeypatch):
        """Partial run sends ⚠️ PARTIAL message."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

        with patch("phase3.telegram_notify.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            notify_loop_done("my_proj", completed=1, failed=1, blocked=0)

        text = mock_post.call_args[1]["json"]["text"]
        assert "⚠️ PARTIAL" in text

    def test_notify_failed_sends_error(self, monkeypatch):
        """notify_loop_failed sends ❌ FAILED message with error."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

        with patch("phase3.telegram_notify.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            notify_loop_failed("my_proj", "something broke")

        text = mock_post.call_args[1]["json"]["text"]
        assert "❌ FAILED" in text
        assert "something broke" in text
