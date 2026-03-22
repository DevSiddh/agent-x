"""
tests/test_failure_classifier.py — Step E1
Tests for phase2/memory/failure_classifier.py
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.memory.failure_classifier import RejectionSummary, classify_rejections


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_entries(path: Path, entries: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _rejected(error: str = "", rejection_reason: str = "") -> dict:
    return {
        "decision": "rejected",
        "error": error,
        "rejection_reason": rejection_reason,
    }


def _accepted() -> dict:
    return {"decision": "accepted", "error": "", "rejection_reason": ""}


# ---------------------------------------------------------------------------
# Path 2 — regex classification from error field
# ---------------------------------------------------------------------------

class TestRegexClassification:

    def test_diff_header_missing_is_prompt_issue(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(error="diff header missing --- a/file")])
        s = classify_rejections(p)
        assert s.by_category["prompt_issue"] == 1
        assert s.total_rejected == 1

    def test_wrong_file_path_is_context_issue(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(error="wrong file path in diff")])
        s = classify_rejections(p)
        assert s.by_category["context_issue"] == 1

    def test_tests_still_fail_is_logic_issue(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(error="tests still fail after patch")])
        s = classify_rejections(p)
        assert s.by_category["logic_issue"] == 1

    def test_exceeds_15_lines_is_size_issue(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(error="exceeds 15 lines limit")])
        s = classify_rejections(p)
        assert s.by_category["size_issue"] == 1

    def test_cve_is_security_issue(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(error="CVE-2024-1234 vulnerability found")])
        s = classify_rejections(p)
        assert s.by_category["security_issue"] == 1

    def test_unrecognised_reason_is_unknown(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(error="something completely unrecognised xyz123")])
        s = classify_rejections(p)
        assert s.by_category["unknown"] == 1
        assert len(s.unknown_reasons) == 1


# ---------------------------------------------------------------------------
# Path 1 — rejection_reason already set
# ---------------------------------------------------------------------------

class TestDirectCategory:

    def test_valid_category_used_directly(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(rejection_reason="logic_issue")])
        s = classify_rejections(p)
        assert s.by_category["logic_issue"] == 1

    def test_security_issue_direct(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(rejection_reason="security_issue")])
        s = classify_rejections(p)
        assert s.by_category["security_issue"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_file_returns_zeros(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        p.write_text("")
        s = classify_rejections(p)
        assert s.total_rejected == 0
        assert s.by_category.get("logic_issue", 0) == 0

    def test_missing_file_returns_zeros(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.jsonl"
        s = classify_rejections(p)
        assert s.total_rejected == 0

    def test_accepted_entries_not_counted(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_accepted(), _accepted(), _rejected(error="diff header missing")])
        s = classify_rejections(p)
        assert s.total_rejected == 1

    def test_corrupt_line_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        with open(p, "w") as f:
            f.write("{corrupt json\n")
            f.write(json.dumps(_rejected(error="diff header missing")) + "\n")
        s = classify_rejections(p)
        assert s.total_rejected == 1

    def test_never_raises_on_missing_file(self, tmp_path: Path) -> None:
        result = classify_rejections(tmp_path / "does_not_exist.jsonl")
        assert isinstance(result, RejectionSummary)


# ---------------------------------------------------------------------------
# top_issue + recommendation
# ---------------------------------------------------------------------------

class TestTopIssue:

    def test_top_issue_is_highest_count_category(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [
            _rejected(error="diff header missing"),
            _rejected(error="diff header missing"),
            _rejected(error="tests still fail"),
        ])
        s = classify_rejections(p)
        assert s.top_issue == "prompt_issue"

    def test_recommendation_populated(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [_rejected(error="tests still fail")])
        s = classify_rejections(p)
        assert len(s.recommendation) > 0

    def test_percentages_sum_to_100(self, tmp_path: Path) -> None:
        p = tmp_path / "m.jsonl"
        _write_entries(p, [
            _rejected(error="diff header missing"),
            _rejected(error="tests still fail"),
            _rejected(error="CVE-2024-0001 vulnerability"),
            _rejected(error="exceeds 15 lines"),
        ])
        s = classify_rejections(p)
        total_pct = sum(s.by_category_pct.values())
        assert abs(total_pct - 100.0) < 0.1
