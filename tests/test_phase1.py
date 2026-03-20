"""
Phase 1 Tests
Covers: hmac_validator, cleaner, dataset schema
"""

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import pytest

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase1.webhook.hmac_validator import validate_raw as validate
from phase1.log_fetcher.cleaner import clean, extract_error_window, clean_and_extract
from phase1.dataset.schema import validate_jsonl_record, FAILURE_CATEGORIES


# ── HMAC Validator ────────────────────────────────────────────────────────────

class TestHmacValidator:

    def _make_sig(self, body: bytes, secret: str) -> str:
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
        body = b'{"action":"completed"}'
        sig  = self._make_sig(body, "test-secret")
        assert validate(body, sig) is True

    def test_invalid_signature(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
        body = b'{"action":"completed"}'
        assert validate(body, "sha256=badhash") is False

    def test_missing_secret_raises(self, monkeypatch):
        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        with pytest.raises(EnvironmentError):
            validate(b"body", "sha256=anything")

    def test_empty_signature_returns_false(self, monkeypatch):
        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
        assert validate(b"body", "") is False


# ── Log Cleaner ───────────────────────────────────────────────────────────────

class TestCleaner:

    def test_strips_timestamps(self):
        lines = ["2024-03-15T14:22:01.123Z ERROR something failed"]
        cleaned = clean(lines)
        assert cleaned == ["ERROR something failed"]

    def test_strips_ansi_codes(self):
        lines = ["\x1b[31mERROR\x1b[0m something failed"]
        cleaned = clean(lines)
        assert "ERROR something failed" in cleaned[0]

    def test_drops_blank_lines(self):
        lines = ["ERROR: fail", "   ", "", "next line"]
        cleaned = clean(lines)
        assert "" not in cleaned
        assert "   " not in cleaned

    def test_drops_github_noise(self):
        lines = [
            "Set up job",
            "Run actions/checkout@v4",
            "Post job cleanup",
            "ERROR: real error here",
        ]
        cleaned = clean(lines)
        assert len(cleaned) == 1
        assert "real error here" in cleaned[0]

    def test_extract_error_window_finds_error_zone(self):
        lines = ["line1", "line2", "ModuleNotFoundError: no module", "line4", "line5"]
        window = extract_error_window(lines, window=3)
        assert any("ModuleNotFoundError" in l for l in window)

    def test_extract_error_window_falls_back_to_tail(self):
        lines = [f"line{i}" for i in range(20)]
        window = extract_error_window(lines, window=5)
        assert window == lines[-5:]

    def test_clean_and_extract_pipeline(self):
        raw = [
            "2024-03-15T14:22:01.123Z Set up job",
            "2024-03-15T14:22:02.000Z ModuleNotFoundError: No module named 'pkg_resources'",
            "2024-03-15T14:22:02.001Z ERROR: pip install failed",
        ]
        result = clean_and_extract(raw, window=10)
        assert any("ModuleNotFoundError" in l for l in result)
        assert not any("Set up job" in l for l in result)


# ── Dataset Schema ─────────────────────────────────────────────────────────────

class TestDatasetSchema:

    def _valid_record(self) -> dict:
        return {
            "id": "syn_001",
            "description": "test case",
            "failure_category": "DependencyError",
            "error_log": ["ModuleNotFoundError: No module named 'pkg_resources'"],
            "expected_fix": "pip install setuptools",
            "expected_patch": "--- a/req.txt\n+++ b/req.txt\n@@ -1 +1,2 @@\n+setuptools",
            "bug_signature": "DependencyError:pkg_resources:requirements.txt",
        }

    def test_valid_record_passes(self):
        assert validate_jsonl_record(self._valid_record()) == []

    def test_missing_field_caught(self):
        record = self._valid_record()
        del record["failure_category"]
        errors = validate_jsonl_record(record)
        assert any("failure_category" in e for e in errors)

    def test_bad_failure_category_caught(self):
        record = self._valid_record()
        record["failure_category"] = "WeirdError"
        errors = validate_jsonl_record(record)
        assert any("failure_category" in e for e in errors)

    def test_bad_bug_signature_format_caught(self):
        record = self._valid_record()
        record["bug_signature"] = "no colons here"
        errors = validate_jsonl_record(record)
        assert any("bug_signature" in e for e in errors)

    def test_all_synthetic_cases_valid(self):
        """Load synthetic.jsonl and validate every record."""
        jsonl_path = Path(__file__).parents[1] / "phase1/dataset/synthetic.jsonl"
        assert jsonl_path.exists(), "synthetic.jsonl not found"
        with open(jsonl_path) as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                errors = validate_jsonl_record(record)
                assert errors == [], f"syn record {i} has errors: {errors}"

    def test_all_failure_categories_covered(self):
        """Every known failure category has at least one synthetic case."""
        jsonl_path = Path(__file__).parents[1] / "phase1/dataset/synthetic.jsonl"
        categories_seen = set()
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    categories_seen.add(record.get("failure_category"))
        for cat in ("DependencyError", "EnvironmentError", "ConfigError", "RuntimeError"):
            assert cat in categories_seen, f"No synthetic case for {cat}"
