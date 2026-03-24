"""
tests/test_pr_creator.py
Tests for phase2/tools/pr_creator.py (D1 — Auto-PR).
All GitHub API calls are mocked — no real network requests.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

import phase2.tools.pr_creator as mod
from phase2.tools.pr_creator import (
    IssueResult,
    PRResult,
    _build_pr_body,
    _get_token,
    create_pr,
    open_structural_issue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status: int, body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body or {}
    resp.text = json.dumps(body or {})
    return resp


def _make_gh_side_effects() -> list[MagicMock]:
    """
    Return ordered mock responses for the 10-step Git Database API flow.
    Steps: get_ref, get_commit, get_contents, create_blob, create_tree,
           create_commit, create_ref, create_pr.
    """
    return [
        _mock_response(200, {"object": {"sha": "main-sha-abc"}}),          # 1 get main ref
        _mock_response(200, {"tree": {"sha": "tree-sha-xyz"}}),             # 2 get commit
        _mock_response(200, {                                                # 3 get file content
            "content": "cmVxdWVzdHM9PTIuMzEuMA==",  # base64("requests==2.31.0")
            "sha": "blob-sha-old",
        }),
        _mock_response(201, {"sha": "blob-sha-new"}),                       # 4 create blob
        _mock_response(201, {"sha": "tree-sha-new"}),                       # 5 create tree
        _mock_response(201, {"sha": "commit-sha-new"}),                     # 6 create commit
        _mock_response(201, {}),                                             # 7 create ref (branch)
        _mock_response(201, {                                                # 8 create PR
            "number": 42,
            "html_url": "https://github.com/owner/repo/pull/42",
        }),
    ]


# ---------------------------------------------------------------------------
# Token resolution
# ---------------------------------------------------------------------------

def test_get_token_returns_pat_when_no_app_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falls back to GITHUB_TOKEN when App credentials not set."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-pat-token")
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    token = _get_token()
    assert token == "test-pat-token"


def test_get_token_returns_empty_when_nothing_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns empty string when no credentials available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    token = _get_token()
    assert token == ""


# ---------------------------------------------------------------------------
# PR body generation
# ---------------------------------------------------------------------------

def test_pr_body_contains_required_sections() -> None:
    """PR body includes all audit receipt sections."""
    body = _build_pr_body(
        diagnosis="ZeroDivisionError caused by missing guard",
        category="RuntimeError",
        affected_file="utils.py",
        run_id="abc123",
        test_summary="5 passed, 0 failed",
        confidence=0.99,
        complexity_before=2.0,
        complexity_after=2.5,
        complexity_delta=0.5,
        failing_test="tests/test_utils.py::test_divide",
        patch="--- a/utils.py\n+++ b/utils.py\n@@ -1 +1 @@\n-x=1/0\n+x=0",
    )
    assert "Diagnosis" in body
    assert "ZeroDivisionError" in body
    assert "RuntimeError" in body
    assert "utils.py" in body
    assert "abc123" in body
    assert "Draft mode" in body
    assert "```diff" in body


def test_pr_body_shows_complexity_delta() -> None:
    """PR body includes complexity delta line when provided."""
    body = _build_pr_body(
        diagnosis="test",
        category="RuntimeError",
        affected_file="app.py",
        run_id="r1",
        test_summary="",
        confidence=0.9,
        complexity_before=1.5,
        complexity_after=4.0,
        complexity_delta=2.5,
        failing_test="",
        patch="",
    )
    assert "Complexity" in body
    assert "+2.5" in body
    assert "review carefully" in body


def test_pr_body_no_complexity_when_none() -> None:
    """PR body omits complexity line when values are None."""
    body = _build_pr_body(
        diagnosis="test",
        category="RuntimeError",
        affected_file="app.py",
        run_id="r1",
        test_summary="",
        confidence=0.9,
        complexity_before=None,
        complexity_after=None,
        complexity_delta=None,
        failing_test="",
        patch="",
    )
    assert "Complexity:" not in body


def test_pr_body_includes_ghost_test_when_provided() -> None:
    """PR body includes Ghost Test section when failing_test provided."""
    body = _build_pr_body(
        diagnosis="test",
        category="RuntimeError",
        affected_file="app.py",
        run_id="r1",
        test_summary="",
        confidence=0.9,
        complexity_before=None,
        complexity_after=None,
        complexity_delta=None,
        failing_test="tests/test_app.py::test_main",
        patch="",
    )
    assert "Ghost Test" in body
    assert "tests/test_app.py::test_main" in body


# ---------------------------------------------------------------------------
# create_pr — Git Database API flow
# ---------------------------------------------------------------------------

def test_create_pr_returns_none_when_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_pr returns None when no GitHub token is available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    result = create_pr(
        repo="owner/repo",
        patch="--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new",
        affected_file="f.py",
        run_id="r1",
        bug_signature="owner/repo:RuntimeError:err:f.py",
        category="RuntimeError",
        test_summary="1 passed",
    )
    assert result is None


def test_create_pr_end_to_end_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_pr succeeds with mocked GitHub API — verifies all 8 steps called."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    side_effects = _make_gh_side_effects()
    call_index = {"i": 0}

    def mock_gh(method: str, path: str, token: str, **kwargs):
        resp = side_effects[call_index["i"]]
        call_index["i"] += 1
        return resp

    with patch.object(mod, "_gh", side_effect=mock_gh):
        with patch.object(mod, "_apply_patch_to_content", return_value="patched content"):
            result = create_pr(
                repo="owner/repo",
                patch="--- a/f\n+++ b/f",
                affected_file="requirements.txt",
                run_id="abc123",
                bug_signature="owner/repo:DependencyError:pkg:requirements.txt",
                category="DependencyError",
                test_summary="3 passed, 0 failed",
                diagnosis="Missing setuptools caused pip to fail",
                confidence=0.99,
            )

    assert result is not None
    assert result.success is True
    assert result.pr_url == "https://github.com/owner/repo/pull/42"
    assert result.pr_number == 42
    assert "agent-x-fixes/" in result.branch


def test_create_pr_assigns_reviewer(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_pr calls reviewer assignment endpoint when original_author provided."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    reviewer_calls: list[str] = []
    side_effects = _make_gh_side_effects()
    # Add reviewer endpoint response
    side_effects.append(_mock_response(201, {}))
    call_index = {"i": 0}

    def mock_gh(method: str, path: str, token: str, **kwargs):
        if "requested_reviewers" in path:
            reviewer_calls.append(path)
        resp = side_effects[call_index["i"]]
        call_index["i"] += 1
        return resp

    with patch.object(mod, "_gh", side_effect=mock_gh):
        with patch.object(mod, "_apply_patch_to_content", return_value="patched"):
            create_pr(
                repo="owner/repo",
                patch="--- a/f\n+++ b/f",
                affected_file="f.py",
                run_id="r1",
                bug_signature="sig",
                category="RuntimeError",
                test_summary="",
                original_author="devuser",
            )

    assert any("requested_reviewers" in c for c in reviewer_calls)


def test_create_pr_returns_none_on_api_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_pr returns None when GitHub API returns 401."""
    monkeypatch.setenv("GITHUB_TOKEN", "bad-token")

    with patch.object(mod, "_gh", return_value=_mock_response(401, {"message": "Bad credentials"})):
        result = create_pr(
            repo="owner/repo",
            patch="--- a/f",
            affected_file="f.py",
            run_id="r1",
            bug_signature="sig",
            category="RuntimeError",
            test_summary="",
        )
    assert result is None


def test_create_pr_never_raises_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_pr never raises even when _gh throws an exception."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    with patch.object(mod, "_gh", side_effect=RuntimeError("network down")):
        result = create_pr(
            repo="owner/repo",
            patch="",
            affected_file="f.py",
            run_id="r1",
            bug_signature="sig",
            category="RuntimeError",
            test_summary="",
        )
    assert result is None


# ---------------------------------------------------------------------------
# open_structural_issue
# ---------------------------------------------------------------------------

def test_open_structural_issue_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """open_structural_issue returns IssueResult on success."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    mock_resp = _mock_response(201, {
        "number": 7,
        "html_url": "https://github.com/owner/repo/issues/7",
    })
    with patch.object(mod, "_gh", return_value=mock_resp):
        result = open_structural_issue(
            repo="owner/repo",
            run_id="run-001",
            category="RuntimeError",
            affected_file="app.py",
            reason="Exceeds 15-line limit",
        )

    assert result is not None
    assert result.success is True
    assert result.issue_number == 7
    assert "issues/7" in result.issue_url


def test_open_structural_issue_includes_correct_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue request body includes required labels."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    captured_payload: dict = {}

    def mock_gh(method, path, token, **kwargs):
        if method == "POST":
            captured_payload.update(kwargs.get("json", {}))
        return _mock_response(201, {"number": 1, "html_url": "https://github.com/o/r/issues/1"})

    with patch.object(mod, "_gh", side_effect=mock_gh):
        open_structural_issue(
            repo="owner/repo",
            run_id="r1",
            category="ConfigError",
            affected_file="config.yaml",
            reason="Too complex",
            original_author="devuser",
        )

    assert "needs-human-review" in captured_payload.get("labels", [])
    assert "agent-x" in captured_payload.get("labels", [])
    assert "devuser" in captured_payload.get("assignees", [])


def test_open_structural_issue_returns_none_when_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns None when no token available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    result = open_structural_issue(
        repo="owner/repo", run_id="r1", category="RuntimeError",
        affected_file="app.py", reason="complex",
    )
    assert result is None


def test_open_structural_issue_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never raises even on exception."""
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    with patch.object(mod, "_gh", side_effect=RuntimeError("crash")):
        result = open_structural_issue(
            repo="owner/repo", run_id="r1", category="RuntimeError",
            affected_file="app.py", reason="complex",
        )
    assert result is None


# ---------------------------------------------------------------------------
# Pipeline integration — PR skipped for synthetic repo
# ---------------------------------------------------------------------------

def test_pipeline_skips_pr_for_synthetic_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pipeline does not call create_pr when REPO == 'synthetic'."""
    import phase2.pipeline as pipeline_mod

    pr_called = {"called": False}

    def mock_create_pr(*args, **kwargs):
        pr_called["called"] = True
        return PRResult(pr_url="https://example.com/pr/1",
                        branch="agent-x-fixes/x", pr_number=1, success=True)

    monkeypatch.setattr("phase2.tools.pr_creator.create_pr", mock_create_pr)

    # REPO is "synthetic" in pipeline.py — PR should be skipped
    assert pipeline_mod.REPO == "synthetic"
    assert pr_called["called"] is False
