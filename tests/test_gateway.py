"""
tests/test_gateway.py
Tests for phase2/gateway.py — zero-cost direct fix tier.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from phase2.gateway import GatewayResult, check


# ---------------------------------------------------------------------------
# Unit tests — gateway logic
# ---------------------------------------------------------------------------

def test_gateway_miss_no_match():
    """No rule matches → returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        result = check(["AssertionError: discount > 100"], Path(tmp))
    assert result is None


def test_gateway_module_not_found_creates_requirements():
    """ModuleNotFoundError → creates requirements.txt and appends module."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        result = check(["ModuleNotFoundError: No module named 'pandas'"], fixture)
        req_content = (fixture / "requirements.txt").read_text(encoding="utf-8")

    assert result is not None
    assert result.matched_rule == "module_not_found"
    assert result.success is True
    assert "pandas" in req_content


def test_gateway_module_not_found_appends_to_existing():
    """Appends missing module to existing requirements.txt, preserving existing lines."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        (fixture / "requirements.txt").write_text("requests==2.0.0\n", encoding="utf-8")
        result = check(["ModuleNotFoundError: No module named 'numpy'"], fixture)
        req_content = (fixture / "requirements.txt").read_text(encoding="utf-8")

    assert result is not None
    assert "numpy" in req_content
    assert "requests==2.0.0" in req_content  # existing line preserved


def test_gateway_returns_none_when_module_already_present():
    """Module already in requirements.txt → fix returns None → gateway miss."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        (fixture / "requirements.txt").write_text("pandas==2.0.0\n", encoding="utf-8")
        result = check(["ModuleNotFoundError: No module named 'pandas'"], fixture)

    assert result is None


def test_gateway_extracts_top_level_package():
    """Submodule import → only top-level package added to requirements."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp)
        result = check(
            ["ModuleNotFoundError: No module named 'sklearn.feature_extraction'"],
            fixture,
        )
        req_content = (fixture / "requirements.txt").read_text(encoding="utf-8")

    assert result is not None
    assert "sklearn" in req_content
    assert "sklearn.feature_extraction" not in req_content


# ---------------------------------------------------------------------------
# Pipeline integration tests
# ---------------------------------------------------------------------------

def test_pipeline_gateway_hit_skips_context_builder(monkeypatch, tmp_path):
    """Gateway hit + tests pass → accepted with model_used='gateway', ContextBuilder never called."""
    import phase2.memory.store as mem_store
    monkeypatch.setattr(mem_store, "_memory_path", lambda: tmp_path / "memory.jsonl")

    from phase2.executor.regression import TestReport
    from phase2.executor.runner import ApplyResult
    from phase2 import pipeline

    gw_hit = GatewayResult(
        matched_rule="module_not_found",
        patch_applied="appended pandas to requirements.txt",
        success=True,
    )
    passing_report = TestReport(passed=True, total=5, failed_tests=[], exit_code=0, raw="5 passed")

    monkeypatch.setattr("phase2.gateway.check", lambda *a, **kw: gw_hit)
    monkeypatch.setattr("phase2.pipeline.run_tests", lambda *a, **kw: passing_report)
    monkeypatch.setattr("phase2.pipeline.rollback", lambda *a, **kw: None)
    monkeypatch.setattr("phase2.pipeline._ensure_fixture_repo", lambda *a, **kw: None)
    monkeypatch.setattr(
        "phase2.memory.similarity.MemoryEngine.find_similar", lambda *a, **kw: None
    )

    ctx_calls = []
    monkeypatch.setattr(
        "phase2.pipeline.build_context",
        lambda *a, **kw: ctx_calls.append(1) or "ctx",
    )

    result = pipeline.run("syn_001")

    assert result.decision == "accepted"
    assert result.model_used == "gateway"
    assert len(ctx_calls) == 0  # ContextBuilder never called


def test_pipeline_gateway_tests_fail_falls_through(monkeypatch, tmp_path):
    """Gateway hit but tests fail → pipeline falls through to full pipeline."""
    import phase2.memory.store as mem_store
    monkeypatch.setattr(mem_store, "_memory_path", lambda: tmp_path / "memory.jsonl")

    from phase2.executor.regression import TestReport
    from phase2 import pipeline

    gw_hit = GatewayResult(
        matched_rule="module_not_found",
        patch_applied="appended pandas to requirements.txt",
        success=True,
    )
    failing_report = TestReport(passed=False, total=5, failed_tests=["test_a"], exit_code=1, raw="1 failed")
    passing_report = TestReport(passed=True, total=5, failed_tests=[], exit_code=0, raw="5 passed")

    call_count = {"run_tests": 0}
    def mock_run_tests(*a, **kw):
        call_count["run_tests"] += 1
        # First call (gateway) fails, subsequent calls pass
        return failing_report if call_count["run_tests"] == 1 else passing_report

    monkeypatch.setattr("phase2.gateway.check", lambda *a, **kw: gw_hit)
    monkeypatch.setattr("phase2.pipeline.run_tests", mock_run_tests)
    monkeypatch.setattr("phase2.pipeline.run_tests_stable", lambda *a, **kw: passing_report)
    monkeypatch.setattr("phase2.pipeline.rollback", lambda *a, **kw: None)
    monkeypatch.setattr("phase2.pipeline._ensure_fixture_repo", lambda *a, **kw: None)
    monkeypatch.setattr(
        "phase2.memory.similarity.MemoryEngine.find_similar", lambda *a, **kw: None
    )

    ctx_calls = []
    monkeypatch.setattr(
        "phase2.pipeline.build_context",
        lambda *a, **kw: ctx_calls.append(1) or "mocked context",
    )

    from phase2.patch_gen.worker import WorkerResult
    from phase2.patch_gen.sanitiser import SanitiserResult
    _diff = "--- a/requirements.txt\n+++ b/requirements.txt\n@@ -1 +1,2 @@\n pandas\n+numpy\n"
    mock_worker = WorkerResult(
        diff=_diff,
        raw_response=_diff,
        sanitiser_result=SanitiserResult(passed=True, diff=_diff, line_count=2, rejection_reason=""),
        model_used="deepseek-chat",
        attempt=1,
    )
    from phase2.executor.runner import ApplyResult
    monkeypatch.setattr("phase2.pipeline.generate_patch", lambda *a, **kw: mock_worker)
    monkeypatch.setattr("phase2.pipeline.apply_patch", lambda *a, **kw: ApplyResult(success=True, stdout="", stderr="", error=""))
    monkeypatch.setattr("phase2.pipeline.check_regression", lambda *a, **kw: False)

    result = pipeline.run("syn_001")

    # ContextBuilder WAS called — fell through
    assert len(ctx_calls) > 0
