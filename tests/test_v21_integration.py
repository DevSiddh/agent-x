"""
tests/test_v21_integration.py — v2.1 integration tests.

Uses real SQLite DBs (tmp_path) but mocks GitHub API + pipeline internals.
Validates the full queue → process_next → MemoryEntry → memory.jsonl flow.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import phase3.webhook_worker as ww
import phase3.runner as runner_mod
from phase3.webhook_worker import already_processed, init_dedup_db, mark_processed


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_dbs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    queue_db = tmp_path / "queue.db"
    dedup_db = tmp_path / "dedup.db"
    memory_file = tmp_path / "memory.jsonl"

    monkeypatch.setattr(ww, "_queue_db_path", lambda: queue_db)
    monkeypatch.setattr(ww, "_dedup_db_path", lambda: dedup_db)

    # Redirect memory store to tmp file
    import phase2.memory.store as store_mod
    monkeypatch.setattr(store_mod, "_memory_path", lambda: memory_file)

    conn = sqlite3.connect(str(queue_db))
    conn.execute("""
        CREATE TABLE webhook_queue (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_name     TEXT NOT NULL,
            run_id        INTEGER NOT NULL,
            run_attempt   INTEGER NOT NULL DEFAULT 1,
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

    init_dedup_db()


def _enqueue(tmp_path: Path, repo: str, run_id: int, run_attempt: int = 1) -> None:
    queue_db = tmp_path / "queue.db"
    conn = sqlite3.connect(str(queue_db))
    conn.execute(
        "INSERT INTO webhook_queue (repo_name, run_id, run_attempt) VALUES (?, ?, ?)",
        (repo, run_id, run_attempt),
    )
    conn.commit()
    conn.close()


def _mock_pipeline(monkeypatch: pytest.MonkeyPatch, confidence: float = 0.99) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        "phase3.webhook_worker.fetch_real_log",
        lambda repo, run_id, run_attempt: "ModuleNotFoundError: No module named 'foo'\n",
    )

    mock_clf = MagicMock()
    mock_clf.category = "DependencyError"
    mock_clf.confidence = confidence
    mock_clf.keyword = "ModuleNotFoundError"
    mock_clf.affected_file = "requirements.txt"
    mock_clf.bug_signature = "org/repo:DependencyError:ModuleNotFoundError:requirements.txt"
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
    mock_sanitiser.passed = True
    mock_sanitiser.line_count = 4

    mock_worker = MagicMock()
    mock_worker.diff = "--- a/requirements.txt\n+++ b/requirements.txt\n+setuptools\n"
    mock_worker.sanitiser_result = mock_sanitiser
    mock_worker.model_used = "deepseek-chat"
    mock_worker.attempt = 1
    monkeypatch.setattr(
        "phase3.webhook_worker.generate_patch",
        lambda error_lines, classifier_result, context: mock_worker,
    )


# ── Integration: queue → process_next → MemoryEntry → memory.jsonl ─────────────

class TestQueueToMemory:
    def test_event_processed_and_written_to_memory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 101)
        _mock_pipeline(monkeypatch)

        entry = ww.process_next()

        assert entry is not None
        assert entry.repo == "org/repo"
        assert entry.failure_category == "DependencyError"
        assert entry.decision == "accepted"

        # Verify written to memory.jsonl
        memory_file = tmp_path / "memory.jsonl"
        assert memory_file.exists()
        lines = [json.loads(l) for l in memory_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        assert lines[0]["repo"] == "org/repo"
        assert lines[0]["failure_category"] == "DependencyError"

    def test_memory_entry_has_github_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 102)
        _mock_pipeline(monkeypatch)

        entry = ww.process_next()
        assert entry is not None
        assert entry.source == "github_webhook"

    def test_duplicate_event_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 103)
        _enqueue(tmp_path, "org/repo", 103)
        _mock_pipeline(monkeypatch)

        first = ww.process_next()
        second = ww.process_next()  # same run_id — deduped

        assert first is not None
        assert second is None

    def test_non_failure_event_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 104)
        monkeypatch.setattr(ww, "should_process", lambda event: False)

        result = ww.process_next()
        assert result is None

    def test_low_confidence_observer_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 105)
        _mock_pipeline(monkeypatch, confidence=0.40)

        generate_calls = []
        monkeypatch.setattr(
            "phase3.webhook_worker.generate_patch",
            lambda *a, **kw: generate_calls.append(1),
        )

        entry = ww.process_next()
        assert entry is not None
        assert entry.decision == "abstained"
        assert len(generate_calls) == 0

    def test_queue_row_marked_done_after_processing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue(tmp_path, "org/repo", 106)
        _mock_pipeline(monkeypatch)

        ww.process_next()

        queue_db = tmp_path / "queue.db"
        conn = sqlite3.connect(str(queue_db))
        rows = conn.execute(
            "SELECT status FROM webhook_queue WHERE run_id=106"
        ).fetchall()
        conn.close()
        assert rows[0][0] == "done"


# ── Runner poll loop ───────────────────────────────────────────────────────────

class TestRunner:
    def test_poll_and_process_calls_process_next(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        call_count = 0

        def mock_process_next() -> None:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt
            return None

        sleep_calls: list[int] = []
        monkeypatch.setattr(runner_mod, "process_next", mock_process_next)
        monkeypatch.setattr(runner_mod.time, "sleep", lambda s: sleep_calls.append(s))

        runner_mod.poll_and_process(interval_seconds=3)

        assert call_count == 2
        assert 3 in sleep_calls

    def test_runner_exits_cleanly_on_keyboard_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            runner_mod, "process_next", lambda: (_ for _ in ()).throw(KeyboardInterrupt)
        )
        monkeypatch.setattr(runner_mod.time, "sleep", lambda s: None)

        # Should not raise
        runner_mod.poll_and_process(interval_seconds=1)

    def test_runner_logs_processed_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from phase2.memory.store import build_default_entry

        mock_entry = build_default_entry(run_id="test-run", repo="org/repo")
        mock_entry = mock_entry.model_copy(update={
            "failure_category": "DependencyError",
            "confidence_score": 0.99,
            "decision": "accepted",
        })

        call_count = 0

        def mock_process_next():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_entry
            raise KeyboardInterrupt

        monkeypatch.setattr(runner_mod, "process_next", mock_process_next)
        monkeypatch.setattr(runner_mod.time, "sleep", lambda s: None)

        runner_mod.poll_and_process(interval_seconds=1)
        assert call_count == 2
