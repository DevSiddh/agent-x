"""
Dataset Schema — Phase 1
Defines and validates the structure of synthetic test cases
stored in synthetic.jsonl.
"""

from dataclasses import dataclass
from typing import Literal

FAILURE_CATEGORIES = (
    "DependencyError",
    "EnvironmentError",
    "ConfigError",
    "RuntimeError",
    "BuildError",
)

DECISIONS = ("accepted", "rejected", "escalated", "abstained", "structural")


@dataclass
class SyntheticCase:
    """One synthetic CI/CD failure test case."""

    id:               str                          # e.g. "syn_001"
    description:      str                          # human-readable
    failure_category: str                          # one of FAILURE_CATEGORIES
    error_log:        list[str]                    # simulated raw log lines
    expected_fix:     str                          # description of correct fix
    expected_patch:   str                          # unified diff of correct patch
    bug_signature:    str                          # ErrorType:keyword:file

    def validate(self) -> list[str]:
        """Return list of validation errors, empty if valid."""
        errors = []
        if not self.id.startswith("syn_"):
            errors.append(f"id must start with 'syn_', got: {self.id}")
        if self.failure_category not in FAILURE_CATEGORIES:
            errors.append(f"Unknown failure_category: {self.failure_category}")
        if not self.error_log:
            errors.append("error_log must not be empty")
        parts = self.bug_signature.split(":")
        if len(parts) != 4:
            errors.append(f"bug_signature must be repo:ErrorType:keyword:file (4 parts), got: {self.bug_signature}")
        return errors


def validate_jsonl_record(record: dict) -> list[str]:
    """
    Validate a raw dict loaded from synthetic.jsonl.
    Returns list of error strings, empty if valid.
    """
    required = [
        "id", "description", "failure_category",
        "error_log", "expected_fix", "expected_patch", "bug_signature",
    ]
    errors = []
    for field in required:
        if field not in record:
            errors.append(f"Missing required field: {field}")

    if "failure_category" in record:
        if record["failure_category"] not in FAILURE_CATEGORIES:
            errors.append(f"Unknown failure_category: {record['failure_category']}")

    if "bug_signature" in record:
        parts = record["bug_signature"].split(":")
        if len(parts) != 4:
            errors.append(f"Invalid bug_signature format (expected repo:ErrorType:keyword:file): {record['bug_signature']}")

    return errors
