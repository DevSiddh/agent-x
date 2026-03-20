"""
tests/test_classifier.py
Step 3 — phase2/classifier/regex_pass.py + safety_gate.py
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.classifier.regex_pass import ClassifierResult, classify
from phase2.classifier.safety_gate import GateDecision, check

JSONL_PATH = Path(__file__).resolve().parents[1] / "phase1" / "dataset" / "synthetic.jsonl"


def load_cases() -> dict[str, dict]:
    cases = {}
    with open(JSONL_PATH) as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                cases[case["id"]] = case
    return cases


CASES = load_cases()
REPO = "test/repo"

EXPECTED = {
    "syn_001": {"category": "DependencyError", "keyword": "ModuleNotFoundError"},
    "syn_002": {"category": "EnvironmentError", "keyword": "no_build_isolation"},
    "syn_003": {"category": "ConfigError",      "keyword": "no_such_table"},
    "syn_004": {"category": "RuntimeError",     "keyword": "pydantic_namespace"},
    "syn_005": {"category": "EnvironmentError", "keyword": "stale_pycache"},
}


# ── ClassifierResult model ─────────────────────────────────────────────────

class TestClassifierResult:

    def test_valid_pydantic_model(self) -> None:
        r = ClassifierResult(
            category="DependencyError",
            confidence=0.99,
            matched_pattern=r"ModuleNotFoundError",
            keyword="pkg_resources",
            affected_file="requirements.txt",
            bug_signature="repo:DependencyError:pkg_resources:requirements.txt",
        )
        assert r.category == "DependencyError"
        assert 0.0 <= r.confidence <= 1.0

    def test_confidence_bounds(self) -> None:
        with pytest.raises(Exception):
            ClassifierResult(
                category="DependencyError",
                confidence=1.5,  # out of range
                matched_pattern="x",
                keyword="x",
                affected_file="x",
                bug_signature="x",
            )


# ── All 5 synthetic cases ──────────────────────────────────────────────────

@pytest.mark.parametrize("case_id", list(EXPECTED.keys()))
def test_correct_category(case_id: str) -> None:
    case = CASES[case_id]
    result = classify(case["error_log"], repo=REPO)
    assert result.category == EXPECTED[case_id]["category"], (
        f"{case_id}: expected {EXPECTED[case_id]['category']}, got {result.category}"
    )


@pytest.mark.parametrize("case_id", list(EXPECTED.keys()))
def test_correct_keyword(case_id: str) -> None:
    case = CASES[case_id]
    result = classify(case["error_log"], repo=REPO)
    assert result.keyword == EXPECTED[case_id]["keyword"], (
        f"{case_id}: expected keyword {EXPECTED[case_id]['keyword']}, got {result.keyword}"
    )


@pytest.mark.parametrize("case_id", list(EXPECTED.keys()))
def test_confidence_above_threshold(case_id: str) -> None:
    """All clear synthetic cases must score >= 0.85 (P5 — calibration baseline)."""
    case = CASES[case_id]
    result = classify(case["error_log"], repo=REPO)
    assert result.confidence >= 0.85, (
        f"{case_id}: confidence {result.confidence} below 0.85"
    )


@pytest.mark.parametrize("case_id", list(EXPECTED.keys()))
def test_bug_signature_contains_repo(case_id: str) -> None:
    """bug_signature must always start with repo prefix (P12)."""
    case = CASES[case_id]
    result = classify(case["error_log"], repo=REPO)
    assert result.bug_signature.startswith(REPO), (
        f"{case_id}: bug_signature missing repo prefix: {result.bug_signature}"
    )


@pytest.mark.parametrize("case_id", list(EXPECTED.keys()))
def test_bug_signature_format(case_id: str) -> None:
    """bug_signature must have 4 colon-separated parts: repo:ErrorType:keyword:file"""
    case = CASES[case_id]
    result = classify(case["error_log"], repo=REPO)
    parts = result.bug_signature.split(":")
    assert len(parts) >= 4, f"{case_id}: bug_signature format wrong: {result.bug_signature}"


# ── Safety gate ────────────────────────────────────────────────────────────

class TestSafetyGate:

    def _make_result(self, confidence: float) -> ClassifierResult:
        return ClassifierResult(
            category="DependencyError",
            confidence=confidence,
            matched_pattern="test",
            keyword="test",
            affected_file="test.txt",
            bug_signature=f"{REPO}:DependencyError:test:test.txt",
        )

    def test_passes_when_confidence_above_threshold(self) -> None:
        decision = check(self._make_result(0.90))
        assert decision.passed is True
        assert decision.mode == "repair"

    def test_passes_at_exact_threshold(self) -> None:
        decision = check(self._make_result(0.85))
        assert decision.passed is True

    def test_blocks_when_confidence_below_threshold(self) -> None:
        decision = check(self._make_result(0.84))
        assert decision.passed is False
        assert decision.mode == "observer"

    def test_blocks_at_zero_confidence(self) -> None:
        decision = check(self._make_result(0.0))
        assert decision.passed is False
        assert decision.mode == "observer"

    def test_returns_gate_decision_model(self) -> None:
        decision = check(self._make_result(0.99))
        assert isinstance(decision, GateDecision)
        assert decision.reason != ""

    def test_all_synthetic_cases_pass_gate(self) -> None:
        """All 5 synthetic cases must pass the safety gate."""
        for case_id, case in CASES.items():
            result = classify(case["error_log"], repo=REPO)
            decision = check(result)
            assert decision.passed is True, (
                f"{case_id}: safety gate blocked with confidence {result.confidence}"
            )
