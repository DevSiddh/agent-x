"""
phase3/webhook_worker.py — Real GitHub webhook event processor.

Dequeues events from webhook_queue → filter → dedup → fetch log
→ clean → classify → run pipeline from ContextBuilder onwards → MemoryEntry.

Run smoke test:
    python phase3/webhook_worker.py
"""

import io
import os
import sqlite3
import sys
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import structlog

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.classifier.regex_pass import classify
from phase2.classifier.safety_gate import check as gate_check
from phase2.context_builder import build_context
from phase2.logging_config import configure_logging
from phase2.memory.store import MemoryEntry, append, build_default_entry
from phase2.patch_gen.worker import generate_patch
from phase3.log_cleaner_real import cap_log, clean_real_log, extract_failure_window

configure_logging()
log = structlog.get_logger()

# ── DB paths (lazy — never at module level) ────────────────────────────────────

def _queue_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "phase1" / "webhook" / "queue.db"


def _dedup_db_path() -> Path:
    return Path(__file__).resolve().parents[1] / "phase3" / "processed_runs.db"


# ── Dedup DB ───────────────────────────────────────────────────────────────────

def init_dedup_db() -> None:
    """Create processed_runs table if it does not exist."""
    db_path = _dedup_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_runs (
            repo        TEXT    NOT NULL,
            run_id      INTEGER NOT NULL,
            run_attempt INTEGER NOT NULL,
            PRIMARY KEY (repo, run_id, run_attempt)
        )
        """
    )
    conn.commit()
    conn.close()
    log.info("webhook_worker.dedup_db_ready", path=str(db_path))


# ── Initialise dedup table on import ──────────────────────────────────────────
init_dedup_db()


# ── Filter ────────────────────────────────────────────────────────────────────

def should_process(event: dict) -> bool:
    """
    Returns True only for completed workflow_run failure events with a run_id.
    Acts as a second filter (server already pre-filters, this guards against
    any edge-cases or test scenarios).
    """
    result = (
        event.get("action") == "completed"
        and event.get("conclusion") == "failure"
        and "run_id" in event
    )
    if not result:
        log.info(
            "webhook.skipped",
            reason="not_failure",
            action=event.get("action"),
            conclusion=event.get("conclusion"),
        )
    return result


# ── Dedup helpers ──────────────────────────────────────────────────────────────

def already_processed(repo: str, run_id: int, run_attempt: int) -> bool:
    """Returns True if this (repo, run_id, run_attempt) has been processed."""
    conn = sqlite3.connect(str(_dedup_db_path()))
    row = conn.execute(
        "SELECT 1 FROM processed_runs WHERE repo=? AND run_id=? AND run_attempt=?",
        (repo, run_id, run_attempt),
    ).fetchone()
    conn.close()
    return row is not None


def mark_processed(repo: str, run_id: int, run_attempt: int) -> None:
    """Record (repo, run_id, run_attempt) so it is never processed again."""
    conn = sqlite3.connect(str(_dedup_db_path()))
    conn.execute(
        "INSERT OR IGNORE INTO processed_runs (repo, run_id, run_attempt) VALUES (?,?,?)",
        (repo, run_id, run_attempt),
    )
    conn.commit()
    conn.close()
    log.info("webhook_worker.marked_processed", repo=repo, run_id=run_id, attempt=run_attempt)


# ── Log fetcher ───────────────────────────────────────────────────────────────

def fetch_real_log(repo: str, run_id: int, run_attempt: int) -> str:
    """
    Fetch and extract the full log text for a GitHub Actions run.
    GITHUB_TOKEN read lazily — never at module level.
    Exponential backoff on 403: delays 1s, 2s, 4s, max 3 retries.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN not set")

    url = (
        f"https://api.github.com/repos/{repo}/actions/runs/"
        f"{run_id}/attempts/{run_attempt}/logs"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    delays = [1, 2, 4]
    for attempt, delay in enumerate(delays, start=1):
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            break
        if resp.status_code == 403:
            log.warning(
                "github.rate_limit",
                attempt=attempt,
                retry_in=delay,
                run_id=run_id,
            )
            if attempt < len(delays):
                time.sleep(delay)
            continue
        raise RuntimeError(
            f"GitHub API error {resp.status_code} for run {run_id}: {resp.text[:200]}"
        )
    else:
        raise RuntimeError(
            f"GitHub API rate limit exceeded after {len(delays)} retries for run {run_id}"
        )

    parts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith(".txt"):
                parts.append(zf.read(name).decode("utf-8", errors="ignore"))
    return "\n".join(parts)


# ── Main processor ────────────────────────────────────────────────────────────

def process_next() -> MemoryEntry | None:
    """
    Dequeue one event from webhook_queue, run it through the full pipeline,
    and return a MemoryEntry. Returns None if queue is empty, event is filtered,
    or already processed.
    """
    # 1 — Dequeue (mark as processing to prevent double-pickup)
    conn = sqlite3.connect(str(_queue_db_path()))
    row = conn.execute(
        "SELECT id, repo_name, run_id FROM webhook_queue "
        "WHERE status='pending' ORDER BY id LIMIT 1"
    ).fetchone()

    if row is None:
        conn.close()
        log.info("webhook_worker.queue_empty")
        return None

    row_id, repo, run_id = row
    conn.execute(
        "UPDATE webhook_queue SET status='processing' WHERE id=?", (row_id,)
    )
    conn.commit()
    conn.close()

    run_attempt = 1  # run_attempt not stored in queue schema — default to 1
    log.info("webhook_worker.dequeued", repo=repo, run_id=run_id, row_id=row_id)

    # 2 — Filter check (server pre-filters but guard defensively)
    event = {"action": "completed", "conclusion": "failure", "run_id": run_id}
    if not should_process(event):
        _mark_queue_done(row_id)
        return None

    # 3 — Dedup check
    if already_processed(repo, run_id, run_attempt):
        log.info("webhook_worker.dedup_skip", repo=repo, run_id=run_id)
        _mark_queue_done(row_id)
        return None

    run_id_str = str(uuid.uuid4())[:8]
    outcome = build_default_entry(run_id=run_id_str, repo=repo)
    outcome = outcome.model_copy(update={"source": "github_webhook"})

    try:
        # 4 — Fetch log
        raw = fetch_real_log(repo, run_id, run_attempt)
        log.info("webhook_worker.log_fetched", repo=repo, run_id=run_id, bytes=len(raw))

        # 5 — Clean
        capped = cap_log(raw)
        cleaned = clean_real_log(capped)
        window = extract_failure_window(cleaned, n=20)

        # 6 — Classify
        classifier_result = classify(window, repo=repo)
        outcome = outcome.model_copy(update={
            "failure_category": classifier_result.category,
            "bug_signature": classifier_result.bug_signature,
            "confidence_score": classifier_result.confidence,
        })

        # 7 — Confidence gate (real logs: < 0.85 → observer, no guessing)
        if classifier_result.confidence < 0.85:
            log.info(
                "classifier.unknown",
                repo=repo,
                run_id=run_id,
                confidence=classifier_result.confidence,
            )
            outcome = outcome.model_copy(update={
                "decision": "abstained",
                "mode": "observer",
            })
            return outcome

        gate = gate_check(classifier_result)
        outcome = outcome.model_copy(update={"mode": gate.mode})

        # 8 — ContextBuilder (fixture_path is temp — file content unavailable for real repos)
        fixture_path = Path(tempfile.mkdtemp())
        context = build_context(classifier_result, fixture_path, error_lines=window)

        # 8.5 — Agent-Y disabled for real CI logs
        # Real logs are too noisy for deepseek-reasoner to parse reliably.
        # Always falls back anyway — skip the 2 wasted API calls.
        enriched_context = context

        # 9 — Patch generation
        worker_result = generate_patch(
            error_lines=window,
            classifier_result=classifier_result,
            context=enriched_context,
        )

        # 10 — Decision: based on sanitiser (no local git apply for real repos in v2.1)
        decision = "accepted" if worker_result.sanitiser_result.passed else "rejected"
        outcome = outcome.model_copy(update={
            "patch_applied": worker_result.diff,
            "lines_changed": worker_result.sanitiser_result.line_count,
            "model_used": worker_result.model_used,
            "retries_used": worker_result.attempt - 1,
            "decision": decision,
            "sandbox_result": "skipped",  # no local fixture — auto-PR handles apply
        })
        log.info(
            "webhook_worker.pipeline_done",
            repo=repo,
            run_id=run_id,
            decision=decision,
            confidence=classifier_result.confidence,
        )

    except Exception as exc:
        log.error("webhook_worker.pipeline_error", repo=repo, run_id=run_id, error=str(exc))
        outcome = outcome.model_copy(update={
            "decision": "abstained",
            "error": str(exc),
        })

    finally:
        outcome = outcome.model_copy(update={
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        append(outcome)
        mark_processed(repo, run_id, run_attempt)
        _mark_queue_done(row_id)

    return outcome


def _mark_queue_done(row_id: int) -> None:
    """Mark queue row as done — keeps audit trail."""
    try:
        conn = sqlite3.connect(str(_queue_db_path()))
        conn.execute("UPDATE webhook_queue SET status='done' WHERE id=?", (row_id,))
        conn.commit()
        conn.close()
    except Exception as exc:
        log.warning("webhook_worker.queue_update_failed", row_id=row_id, error=str(exc))


# ── Smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sqlite3 as _sqlite3
    from unittest.mock import MagicMock, patch

    print("--- should_process ---")
    assert should_process({"action": "completed", "conclusion": "failure", "run_id": 1})
    assert not should_process({"action": "completed", "conclusion": "success", "run_id": 1})
    assert not should_process({"action": "requested", "conclusion": "failure", "run_id": 1})
    assert not should_process({"action": "completed", "conclusion": "failure"})
    print("should_process  OK")

    print("\n--- already_processed / mark_processed ---")
    import tempfile as _tempfile
    import phase3.webhook_worker as _ww

    tmp_dedup = _tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_dedup.close()
    _ww._dedup_db_path = lambda: Path(tmp_dedup.name)  # type: ignore[method-assign]
    _ww.init_dedup_db()

    assert not _ww.already_processed("repo/test", 123, 1)
    _ww.mark_processed("repo/test", 123, 1)
    assert _ww.already_processed("repo/test", 123, 1)
    assert not _ww.already_processed("repo/test", 123, 2)  # different attempt
    Path(tmp_dedup.name).unlink(missing_ok=True)
    print("dedup  OK")

    print("\n--- process_next with empty queue ---")
    tmp_queue = _tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_queue.close()
    conn = _sqlite3.connect(tmp_queue.name)
    conn.execute("""
        CREATE TABLE webhook_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_name TEXT, run_id INTEGER,
            workflow_name TEXT, branch TEXT, commit_sha TEXT,
            event_ts TEXT, status TEXT DEFAULT 'pending', queued_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    _ww._queue_db_path = lambda: Path(tmp_queue.name)  # type: ignore[method-assign]

    result = _ww.process_next()
    assert result is None
    Path(tmp_queue.name).unlink(missing_ok=True)
    print("empty queue returns None  OK")

    print("\nwebhook_worker.py smoke test PASSED")
    sys.exit(0)
