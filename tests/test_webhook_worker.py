"""
tests/test_webhook_worker.py — Tests for phase3/webhook_worker.py

All GitHub API calls are mocked. Uses temp SQLite DBs so nothing touches
real queue.db or processed_runs.db.
"""

import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase3.webhook_worker as ww
from phase3.webhook_worker import (
    already_processed,
    init_dedup_db,
    mark_processed,
    should_process,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_dbs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect both DBs to temp files for every test."""
    queue_db = tmp_path / "queue.db"
    dedup_db = tmp_path / "dedup.db"

    monkeypatch.setattr(ww, "_queue_db_path", lambda: queue_db)
    monkeypatch.setattr(ww, "_dedup_db_path", lambda: dedup_db)

    # Build queue schema
    conn = sqlite3.connect(str(queue_db))
    conn.execute("""
        CREATE TABLE webhook_queue (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_name     TEXT NOT NULL,
            run_id        INTEGER NOT NULL,
            workflow_name TEXT NOT NULL DEFAULT '',
            branch        TEXT NOT NULL DEFAULT '',
            commit_sha    TEXT NOT NULL DEFAULT '',
            event_ts      TEXT NOT NULL DEFAULT '',
            status        TEXT NOT NULL DEFAULT 'pending',
            queued_at     TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

    # Build dedup schema
    init_dedup_db()


def _enqueue(tmp_path: Path, repo: str, run_id: int) -> None:
    """Insert a pending event into the test queue DB."""
    queue_db = tmp_path / "queue.db"
    conn = sqlite3.connect(str(queue_db))
    conn.execute(
        "INSERT INTO webhook_queue (repo_name, run_id) VALUES (?, ?)",
        (repo, run_id),
    )
    conn.commit()
    conn.close()


# ── should_process ─────────────────────────────────────────────────────────────

class TestShouldProcess:
    def test_true_for_completed_failure(self) -> None:
        event = {"action": "completed", "conclusion": "failure", "run_id": 1}
        assert should_process(event) is True

    def test_false_for_success(self) -> None:
        event = {"action": "completed", "conclusion": "success", "run_id": 1}
        assert should_process(event) is False

    def test_false_for_cancelled(self) -> None:
        event = {"action": "completed", "conclusion": "cancelled", "run_id": 1}
        assert should_process(event) is False

    def test_false_for_non_completed_action(self) -> None:
        event = {"action": "requested", "conclusion": "failure", "run_id": 1}
        assert should_process(event) is False

    def test_false_when_run_id_missing(self) -> None:
        event = {"action": "completed", "conclusion": "failure"}
        assert should_process(event) is False

    def test_false_for_empty_event(self) -> None:
        assert should_process({}) is False


# ── already_processed / mark_processed ────────────────────────────────────────

class TestDedup:
    def test_false_for_new_run(self) -> None:
        assert already_processed("org/repo", 999, 1) is False

    def test_true_after_mark(self) -> None:
        mark_processed("org/repo", 999, 1)
        assert already_processed("org/repo", 999, 1) is True

    def test_different_attempt_not_processed(self) -> None:
        mark_processed("org/repo", 999, 1)
        assert already_processed("org/repo", 999, 2) is False

    def test_different_repo_not_processed(self) -> None:
        mark_processed("org/repo", 999, 1)
        assert already_processed("other/repo", 999, 1) is False

    def test_same_run_not_processed_twice(self) -> None:
        mark_processed("org/repo", 42, 1)
        mark_processed("org/repo", 42, 1)  # INSERT OR IGNORE — should not raise
        assert already_processed("org/repo", 42, 1) is True


# ── fetch_real_log ─────────────────────────────────────────────────────────────

class TestFetchRealLog:
    def _make_zip_bytes(self, content: str = "error log line\n") -> bytes:
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("1_step.txt", content)
        return buf.getvalue()

    def test_exponential_backoff_on_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        call_count = 0
        responses = []

        def mock_get(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            r = MagicMock()
            if call_count < 3:
                r.status_code = 403
                r.text = "rate limited"
            else:
                r.status_code = 200
                r.content = self._make_zip_bytes("actual error\n")
            return r

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        monkeypatch.setattr("phase3.webhook_worker.requests.get", mock_get)
        monkeypatch.setattr("phase3.webhook_worker.time.sleep", lambda s: None)

        result = ww.fetch_real_log("org/repo", 123, 1)
        assert "actual error" in result
        assert call_count == 3

    def test_raises_after_3_failed_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def mock_get(*args: object, **kwargs: object) -> MagicMock:
            r = MagicMock()
            r.status_code = 403
            r.text = "rate limited"
            return r

        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        monkeypatch.setattr("phase3.webhook_worker.requests.get", mock_get)
        monkeypatch.setattr("phase3.webhook_worker.time.sleep", lambda s: None)

        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            ww.fetch_real_log("org/repo", 123, 1)

    def test_raises_on_missing_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(EnvironmentError, match="GITHUB_TOKEN"):
            ww.fetch_real_log("org/repo", 123, 1)


# ── process_next ──────────────────────────────────────────────────────────────

class TestProcessNext:
    def _mock_fetch(self, monkeypatch: pytest.MonkeyPatch, log_text: str) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "test-token")
        monkeypatch.setattr(
            "phase3.webhook_worker.fetch_real_log",
            lambda repo, run_id, run_attempt: log_text,
        )

    def _mock_pipeline(
        self,
        monkeypatch: pytest.MonkeyPatch,
        confidence: float = 0.99,
        patch_passed: bool = True,
    ) -> None:
        mock_clf = MagicMock()
        mock_clf.category = "DependencyError"
        mock_clf.confidence = confidence
        mock_clf.keyword = "ModuleNotFoundError"
        mock_clf.affected_file = "requirements.txt"
        mock_clf.bug_signature = f"org/repo:DependencyError:ModuleNotFoundError:requirements.txt"
        monkeypatch.setattr("phase3.webhook_worker.classify", lambda lines, repo: mock_clf)

        mock_gate = MagicMock()
        mock_gate.passed = True
        mock_gate.mode = "repair"
        monkeypatch.setattr("phase3.webhook_worker.gate_check", lambda r: mock_gate)

        monkeypatch.setattr(
            "phase3.webhook_worker.build_context",
            lambda clf, path, error_lines=None: "mock context",
        )

        mock_sanitiser = MagicMock()
        mock_sanitiser.passed = patch_passed
        mock_sanitiser.line_count = 5

        mock_worker = MagicMock()
        mock_worker.diff = "--- a/requirements.txt\n+++ b/requirements.txt\n"
        mock_worker.sanitiser_result = mock_sanitiser
        mock_worker.model_used = "deepseek-chat"
        mock_worker.attempt = 1
        monkeypatch.setattr(
            "phase3.webhook_worker.generate_patch",
            lambda error_lines, classifier_result, context: mock_worker,
        )

        # Suppress Agent-Y in tests
        monkeypatch.setattr(
            "phase3.webhook_worker.build_context",
            lambda clf, path, error_lines=None: "mock context",
        )

    def test_returns_none_when_queue_empty(self) -> None:
        result = ww.process_next()
        assert result is None

    def test_processes_queued_event(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 111)
        self._mock_fetch(monkeypatch, "ModuleNotFoundError: No module named 'foo'\n")
        self._mock_pipeline(monkeypatch, confidence=0.99)

        # Suppress Agent-Y
        monkeypatch.setattr(
            "phase3.webhook_worker.reason",
            lambda ctx, clf: (_ for _ in ()).throw(Exception("skip")),
            raising=False,
        )

        result = ww.process_next()
        assert result is not None
        assert result.repo == "org/repo"
        assert result.failure_category == "DependencyError"

    def test_returns_none_for_non_failure_event(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 222)
        # Override should_process to return False
        monkeypatch.setattr(ww, "should_process", lambda event: False)
        result = ww.process_next()
        assert result is None

    def test_returns_none_for_already_processed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 333)
        mark_processed("org/repo", 333, 1)
        self._mock_fetch(monkeypatch, "some error\n")
        result = ww.process_next()
        assert result is None

    def test_low_confidence_returns_default_entry_no_pipeline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 444)
        self._mock_fetch(monkeypatch, "some ambiguous log line\n")
        self._mock_pipeline(monkeypatch, confidence=0.50)

        generate_called = []
        monkeypatch.setattr(
            "phase3.webhook_worker.generate_patch",
            lambda *a, **kw: generate_called.append(True),
        )

        result = ww.process_next()
        assert result is not None
        assert result.decision == "abstained"
        assert result.mode == "observer"
        assert len(generate_called) == 0  # pipeline NOT called

    def test_dedup_prevents_double_processing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 555)
        _enqueue(tmp_path, "org/repo", 555)  # same run_id queued twice
        self._mock_fetch(monkeypatch, "ModuleNotFoundError: foo\n")
        self._mock_pipeline(monkeypatch, confidence=0.99)

        monkeypatch.setattr(
            "phase3.webhook_worker.reason",
            lambda ctx, clf: (_ for _ in ()).throw(Exception("skip")),
            raising=False,
        )

        first = ww.process_next()
        second = ww.process_next()  # same run_id — should be deduped
        assert first is not None
        assert second is None  # deduped
