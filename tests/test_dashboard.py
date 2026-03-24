"""
tests/test_dashboard.py
Tests for dashboard/data.py — pure-Python data layer.
No Streamlit imports needed.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

import dashboard.data as data_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    decision: str = "accepted",
    model_used: str = "deepseek-chat",
    failure_category: str = "DependencyError",
    rejection_reason: str = "",
) -> dict[str, Any]:
    return {
        "run_id": "test-run",
        "timestamp": "2026-03-24T00:00:00+00:00",
        "source": "pipeline",
        "repo": "test/repo",
        "failure_category": failure_category,
        "bug_signature": f"test/repo:{failure_category}:kw:file.py",
        "confidence_score": 0.99,
        "mode": "repair",
        "patch_applied": "--- a/f.py\n+++ b/f.py\n",
        "lines_changed": 1,
        "model_used": model_used,
        "sandbox_result": "pass",
        "regression_introduced": False,
        "retries_used": 0,
        "mttr_seconds": 1.0,
        "decision": decision,
        "success_count": 1,
        "fail_count": 0,
        "error": "",
        "test_summary": "1 passed",
        "rejection_reason": rejection_reason,
    }


# ---------------------------------------------------------------------------
# load_entries
# ---------------------------------------------------------------------------

class TestLoadEntries:
    def test_missing_file_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(data_mod, "_memory_path", lambda: Path("/no/such/file.jsonl"))
        assert data_mod.load_entries() == []

    def test_loads_valid_entries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = tmp_path / "memory.jsonl"
        p.write_text(
            json.dumps(_make_entry("accepted")) + "\n"
            + json.dumps(_make_entry("rejected")) + "\n"
        )
        monkeypatch.setattr(data_mod, "_memory_path", lambda: p)
        entries = data_mod.load_entries()
        assert len(entries) == 2

    def test_skips_blank_lines(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = tmp_path / "memory.jsonl"
        p.write_text("\n" + json.dumps(_make_entry()) + "\n\n")
        monkeypatch.setattr(data_mod, "_memory_path", lambda: p)
        assert len(data_mod.load_entries()) == 1

    def test_skips_corrupt_lines(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = tmp_path / "memory.jsonl"
        p.write_text("not-json\n" + json.dumps(_make_entry()) + "\n")
        monkeypatch.setattr(data_mod, "_memory_path", lambda: p)
        assert len(data_mod.load_entries()) == 1


# ---------------------------------------------------------------------------
# load_thompson_state
# ---------------------------------------------------------------------------

class TestLoadThompsonState:
    def test_missing_file_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(data_mod, "_thompson_path", lambda: Path("/no/such/file.json"))
        assert data_mod.load_thompson_state() == {}

    def test_loads_state(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = tmp_path / "thompson_state.json"
        state = {"DependencyError_Python": {"alpha": 10, "beta": 2}}
        p.write_text(json.dumps(state))
        monkeypatch.setattr(data_mod, "_thompson_path", lambda: p)
        loaded = data_mod.load_thompson_state()
        assert loaded["DependencyError_Python"]["alpha"] == 10

    def test_corrupt_file_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = tmp_path / "thompson_state.json"
        p.write_text("not-json")
        monkeypatch.setattr(data_mod, "_thompson_path", lambda: p)
        assert data_mod.load_thompson_state() == {}


# ---------------------------------------------------------------------------
# run_summary
# ---------------------------------------------------------------------------

class TestRunSummary:
    def test_counts_decisions(self) -> None:
        entries = [
            _make_entry("accepted"),
            _make_entry("accepted"),
            _make_entry("rejected"),
            _make_entry("abstained"),
            _make_entry("structural"),
        ]
        summary = data_mod.run_summary(entries)
        assert summary["accepted"] == 2
        assert summary["rejected"] == 1
        assert summary["abstained"] == 1
        assert summary["structural"] == 1
        assert summary["total"] == 5

    def test_empty_entries(self) -> None:
        summary = data_mod.run_summary([])
        assert summary["total"] == 0
        assert summary["accepted"] == 0


# ---------------------------------------------------------------------------
# acceptance_rate
# ---------------------------------------------------------------------------

class TestAcceptanceRate:
    def test_zero_total(self) -> None:
        assert data_mod.acceptance_rate({"total": 0, "accepted": 0}) == 0.0

    def test_half(self) -> None:
        rate = data_mod.acceptance_rate({"total": 10, "accepted": 5})
        assert rate == 50.0

    def test_full(self) -> None:
        rate = data_mod.acceptance_rate({"total": 4, "accepted": 4})
        assert rate == 100.0


# ---------------------------------------------------------------------------
# cost_saved_summary
# ---------------------------------------------------------------------------

class TestCostSavedSummary:
    def test_counts_correctly(self) -> None:
        entries = [
            _make_entry(model_used="deepseek-chat"),
            _make_entry(model_used="deepseek-chat"),
            _make_entry(model_used="memory_reuse"),
            _make_entry(model_used="gateway"),
            _make_entry(model_used="gateway"),
        ]
        cost = data_mod.cost_saved_summary(entries)
        assert cost["deepseek_calls"] == 2
        assert cost["memory_reuse"] == 1
        assert cost["gateway_hits"] == 2
        assert cost["bypassed_total"] == 3
        assert cost["cost_saved_usd"] > 0

    def test_no_bypasses(self) -> None:
        entries = [_make_entry(model_used="deepseek-chat")] * 5
        cost = data_mod.cost_saved_summary(entries)
        assert cost["bypassed_total"] == 0
        assert cost["cost_saved_usd"] == 0.0

    def test_empty(self) -> None:
        cost = data_mod.cost_saved_summary([])
        assert cost["bypassed_total"] == 0


# ---------------------------------------------------------------------------
# thompson_table
# ---------------------------------------------------------------------------

class TestThompsonTable:
    def test_sorted_by_win_rate(self) -> None:
        state = {
            "DependencyError_Python": {"alpha": 5, "beta": 5},   # lower win rate
            "ConfigError_Python": {"alpha": 10, "beta": 1},       # higher win rate
        }
        table = data_mod.thompson_table(state)
        assert table[0]["arm"] == "ConfigError_Python"

    def test_win_rate_formula(self) -> None:
        # alpha=11, beta=1 → trials=9, win_rate = 10/9... let's be exact
        # trials = alpha + beta - 2 = 10
        # win_rate = (alpha - 1) / trials = 10 / 10 = 1.0
        state = {"TestArm_Python": {"alpha": 11, "beta": 1}}
        table = data_mod.thompson_table(state)
        assert table[0]["win_rate"] == 1.0

    def test_empty_state(self) -> None:
        assert data_mod.thompson_table({}) == []

    def test_returns_correct_fields(self) -> None:
        state = {"MyArm_Node": {"alpha": 3, "beta": 2}}
        row = data_mod.thompson_table(state)[0]
        assert "arm" in row
        assert "alpha" in row
        assert "beta" in row
        assert "trials" in row
        assert "win_rate" in row


# ---------------------------------------------------------------------------
# category_breakdown
# ---------------------------------------------------------------------------

class TestCategoryBreakdown:
    def test_counts_categories(self) -> None:
        entries = [
            _make_entry(failure_category="DependencyError"),
            _make_entry(failure_category="DependencyError"),
            _make_entry(failure_category="ConfigError"),
        ]
        cats = data_mod.category_breakdown(entries)
        assert cats["DependencyError"] == 2
        assert cats["ConfigError"] == 1

    def test_empty(self) -> None:
        assert data_mod.category_breakdown([]) == {}


# ---------------------------------------------------------------------------
# rejection_breakdown
# ---------------------------------------------------------------------------

class TestRejectionBreakdown:
    def test_only_counts_non_accepted(self) -> None:
        entries = [
            _make_entry(decision="accepted", rejection_reason=""),
            _make_entry(decision="rejected", rejection_reason="prompt_issue"),
            _make_entry(decision="abstained", rejection_reason="context_issue"),
            _make_entry(decision="structural", rejection_reason=""),
        ]
        rej = data_mod.rejection_breakdown(entries)
        assert "accepted" not in str(rej)
        assert rej.get("prompt_issue") == 1
        assert rej.get("context_issue") == 1
        # empty reason → "unknown"
        assert rej.get("unknown") == 1

    def test_empty(self) -> None:
        assert data_mod.rejection_breakdown([]) == {}
