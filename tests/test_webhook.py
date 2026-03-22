"""
Tests — phase1/webhook
Covers: hmac_validator, server endpoint (queue write, filtering, auth)
"""

import asyncio
import hashlib
import hmac
import json
import os
import sys
import tempfile
from pathlib import Path

import aiosqlite
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Patch DB_PATH before importing server so tests use a temp DB ──────────────
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
_TMP_DB = Path(_tmp_db.name)

import phase1.webhook.server as _server_mod

_server_mod.DB_PATH = _TMP_DB  # redirect before app starts

from phase1.webhook.hmac_validator import validate as _hmac_validate
from phase1.webhook.server import app, enqueue

SECRET = "test-secret"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sig(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _failure_payload(**overrides) -> dict:
    base = {
        "action": "completed",
        "workflow_run": {
            "id": 42,
            "name": "CI",
            "conclusion": "failure",
            "head_branch": "main",
            "head_sha": "abc123",
            "updated_at": "2026-03-20T00:00:00Z",
        },
        "repository": {"full_name": "acme/repo"},
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def set_secret(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)


@pytest.fixture(autouse=True)
def fresh_db():
    """Re-create the queue table before each test."""
    asyncio.get_event_loop().run_until_complete(_reset_db())
    yield


async def _reset_db() -> None:
    async with aiosqlite.connect(_TMP_DB) as db:
        await db.execute("DROP TABLE IF EXISTS webhook_queue")
        await db.execute(
            """
            CREATE TABLE webhook_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_name TEXT NOT NULL,
                run_id INTEGER NOT NULL,
                run_attempt INTEGER NOT NULL DEFAULT 1,
                workflow_name TEXT NOT NULL,
                branch TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                event_ts TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                queued_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await db.commit()


async def _row_count() -> int:
    async with aiosqlite.connect(_TMP_DB) as db:
        async with db.execute("SELECT COUNT(*) FROM webhook_queue") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def _fetch_rows() -> list[dict]:
    async with aiosqlite.connect(_TMP_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM webhook_queue") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ── hmac_validator ────────────────────────────────────────────────────────────

class TestHmacValidator:

    class _Req:
        """Minimal FastAPI Request stub."""
        def __init__(self, body: bytes, sig: str) -> None:
            self._body = body
            self.headers: dict[str, str] = {"X-Hub-Signature-256": sig}

        async def body(self) -> bytes:
            return self._body

    def test_valid_signature(self):
        body = b'{"hello":"world"}'
        sig = _sig(body)
        result = asyncio.get_event_loop().run_until_complete(
            _hmac_validate(self._Req(body, sig))  # type: ignore[arg-type]
        )
        assert result is True

    def test_invalid_signature(self):
        body = b'{"hello":"world"}'
        result = asyncio.get_event_loop().run_until_complete(
            _hmac_validate(self._Req(body, "sha256=badhash"))  # type: ignore[arg-type]
        )
        assert result is False

    def test_missing_signature_returns_false(self):
        body = b'{"hello":"world"}'
        result = asyncio.get_event_loop().run_until_complete(
            _hmac_validate(self._Req(body, ""))  # type: ignore[arg-type]
        )
        assert result is False

    def test_missing_secret_raises(self, monkeypatch):
        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        body = b"body"
        with pytest.raises(EnvironmentError):
            asyncio.get_event_loop().run_until_complete(
                _hmac_validate(self._Req(body, "sha256=anything"))  # type: ignore[arg-type]
            )

    def test_wrong_secret_returns_false(self):
        body = b'{"hello":"world"}'
        sig = _sig(body, secret="other-secret")
        result = asyncio.get_event_loop().run_until_complete(
            _hmac_validate(self._Req(body, sig))  # type: ignore[arg-type]
        )
        assert result is False


# ── /webhook endpoint ─────────────────────────────────────────────────────────

class TestWebhookEndpoint:

    @pytest.fixture(autouse=True)
    def client(self):
        with TestClient(app) as c:
            self._client = c
            yield

    def _post(self, payload: dict, sig_override: str | None = None, event: str = "workflow_run") -> int:
        body = json.dumps(payload).encode()
        sig = sig_override if sig_override is not None else _sig(body)
        r = self._client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": event,
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
        return r.status_code

    # Auth
    def test_valid_failure_returns_200(self):
        assert self._post(_failure_payload()) == 200

    def test_bad_signature_returns_401(self):
        assert self._post(_failure_payload(), sig_override="sha256=badhash") == 401

    def test_missing_signature_returns_401(self):
        assert self._post(_failure_payload(), sig_override="") == 401

    # Filtering
    def test_non_workflow_run_event_returns_200_not_queued(self):
        payload = _failure_payload()
        body = json.dumps(payload).encode()
        r = self._client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sig(body),
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 200
        assert asyncio.get_event_loop().run_until_complete(_row_count()) == 0

    def test_non_completed_action_not_queued(self):
        payload = _failure_payload(action="requested")
        assert self._post(payload) == 200
        assert asyncio.get_event_loop().run_until_complete(_row_count()) == 0

    def test_success_conclusion_not_queued(self):
        payload = _failure_payload()
        payload["workflow_run"]["conclusion"] = "success"
        assert self._post(payload) == 200
        assert asyncio.get_event_loop().run_until_complete(_row_count()) == 0

    # Queue writes
    def test_failure_event_written_to_queue(self):
        self._post(_failure_payload())
        assert asyncio.get_event_loop().run_until_complete(_row_count()) == 1

    def test_queued_row_has_correct_fields(self):
        self._post(_failure_payload())
        rows = asyncio.get_event_loop().run_until_complete(_fetch_rows())
        assert len(rows) == 1
        r = rows[0]
        assert r["repo_name"]     == "acme/repo"
        assert r["run_id"]        == 42
        assert r["workflow_name"] == "CI"
        assert r["branch"]        == "main"
        assert r["commit_sha"]    == "abc123"
        assert r["status"]        == "pending"

    def test_multiple_failure_events_all_queued(self):
        for i in range(3):
            payload = _failure_payload()
            payload["workflow_run"]["id"] = 100 + i
            self._post(payload)
        assert asyncio.get_event_loop().run_until_complete(_row_count()) == 3

    def test_bad_json_returns_400(self):
        body = b"not-json"
        r = self._client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": _sig(body),
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 400
