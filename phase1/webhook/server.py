"""
GitHub Webhook Server — Phase 1
Receives workflow_run failure events from GitHub and writes them
to a SQLite queue for the Agent-X pipeline.

Run:
    uvicorn phase1.webhook.server:app --port 8080
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite
import structlog
from fastapi import FastAPI, Request, Response

# ── Allow project-root imports ────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from phase1.webhook.hmac_validator import validate  # noqa: E402

# ── Logging ───────────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "queue.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS webhook_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_name     TEXT    NOT NULL,
    run_id        INTEGER NOT NULL,
    workflow_name TEXT    NOT NULL,
    branch        TEXT    NOT NULL,
    commit_sha    TEXT    NOT NULL,
    event_ts      TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',
    queued_at     TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""


# ── DB lifecycle ──────────────────────────────────────────────────────────────
async def init_db() -> None:
    """Create queue table if it does not exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_TABLE)
        await db.commit()
    log.info("webhook.db_ready", path=str(DB_PATH))


async def enqueue(
    repo_name: str,
    run_id: int,
    workflow_name: str,
    branch: str,
    commit_sha: str,
    event_ts: str,
) -> int:
    """
    Insert one failure event into the queue.

    Returns:
        The rowid of the inserted record.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO webhook_queue
                (repo_name, run_id, workflow_name, branch, commit_sha, event_ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (repo_name, run_id, workflow_name, branch, commit_sha, event_ts),
        )
        await db.commit()
        row_id: int = cursor.lastrowid  # type: ignore[assignment]
    log.info(
        "webhook.queued",
        repo=repo_name,
        run_id=run_id,
        workflow=workflow_name,
        branch=branch,
        row_id=row_id,
    )
    return row_id


# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    yield


app = FastAPI(title="Agent-X Webhook", lifespan=lifespan)


# ── Endpoint ──────────────────────────────────────────────────────────────────
@app.post("/webhook")
async def webhook(request: Request) -> Response:
    """
    Accept GitHub workflow_run webhook events.

    - Validates HMAC-SHA256 signature → 401 if invalid.
    - Ignores non-failure / non-workflow_run events silently → 200.
    - Extracts key fields and writes to SQLite queue.
    - Returns 200 immediately (fire-and-forget for downstream pipeline).
    """
    # 1 — Signature check
    try:
        valid = await validate(request)
    except EnvironmentError as exc:
        log.error("webhook.secret_missing", error=str(exc))
        return Response(status_code=500)

    if not valid:
        return Response(status_code=401)

    # 2 — Parse body (FastAPI has already cached it)
    body = await request.body()
    try:
        payload: dict = json.loads(body)
    except json.JSONDecodeError:
        log.warning("webhook.bad_json")
        return Response(status_code=400)

    event = request.headers.get("X-GitHub-Event", "")

    # 3 — Filter: workflow_run failures only
    workflow = payload.get("workflow_run", {})
    if not (
        event == "workflow_run"
        and payload.get("action") == "completed"
        and workflow.get("conclusion") == "failure"
    ):
        return Response(status_code=200)

    # 4 — Extract fields
    repo_name: str     = payload.get("repository", {}).get("full_name", "unknown")
    run_id: int        = int(workflow.get("id", 0))
    workflow_name: str = workflow.get("name", "unknown")
    branch: str        = workflow.get("head_branch", "unknown")
    commit_sha: str    = workflow.get("head_sha", "unknown")
    event_ts: str      = workflow.get("updated_at", "unknown")

    # 5 — Write to queue (async, non-blocking from caller's perspective)
    await enqueue(
        repo_name=repo_name,
        run_id=run_id,
        workflow_name=workflow_name,
        branch=branch,
        commit_sha=commit_sha,
        event_ts=event_ts,
    )

    return Response(status_code=200)


# ── Smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import hashlib
    import hmac as _hmac
    import tempfile

    from fastapi.testclient import TestClient

    os.environ["GITHUB_WEBHOOK_SECRET"] = "smoke-secret"

    # Override DB to a temp file so smoke test is self-contained
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    DB_PATH = Path(_tmp.name)  # type: ignore[assignment]
    _tmp.close()

    def _make_sig(body: bytes, secret: str = "smoke-secret") -> str:
        return "sha256=" + _hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    _FAILURE_PAYLOAD = {
        "action": "completed",
        "workflow_run": {
            "id": 99991234,
            "name": "CI",
            "conclusion": "failure",
            "head_branch": "main",
            "head_sha": "abc123def456",
            "updated_at": "2026-03-20T10:00:00Z",
            "logs_url": "https://api.github.com/repos/acme/app/actions/runs/99991234/logs",
        },
        "repository": {"full_name": "acme/app"},
    }

    with TestClient(app) as client:
        body = json.dumps(_FAILURE_PAYLOAD).encode()

        # ── Test 1: valid failure event → 200 ────────────────────────────────
        r = client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": _make_sig(body),
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        print(f"[PASS] failure event accepted: {r.status_code}")

        # ── Test 2: bad signature → 401 ───────────────────────────────────────
        r = client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": "sha256=badhash",
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print(f"[PASS] bad signature rejected: {r.status_code}")

        # ── Test 3: non-failure event → 200, NOT queued ───────────────────────
        success_payload = json.dumps({**_FAILURE_PAYLOAD, "action": "requested"}).encode()
        r = client.post(
            "/webhook",
            content=success_payload,
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": _make_sig(success_payload),
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        print(f"[PASS] non-failure event ignored: {r.status_code}")

        # ── Test 4: verify DB has exactly 1 row (only the failure event) ──────
        import asyncio

        async def _check_db() -> int:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT COUNT(*) FROM webhook_queue") as cur:
                    row = await cur.fetchone()
                    return row[0] if row else 0

        count = asyncio.run(_check_db())
        assert count == 1, f"Expected 1 queued row, got {count}"
        print(f"[PASS] queue has {count} row — only failure event written")

    DB_PATH.unlink(missing_ok=True)
    print("\nserver.py smoke test PASSED")
