"""
phase2/classifier/safety_gate.py
Confidence gate — blocks pipeline if classifier confidence < 0.85.
"""
import sys
from pathlib import Path

import structlog
from pydantic import BaseModel

# Allow direct execution and package import
try:
    from phase2.classifier.regex_pass import ClassifierResult
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from phase2.classifier.regex_pass import ClassifierResult

log = structlog.get_logger()

CONFIDENCE_THRESHOLD = 0.85


class GateDecision(BaseModel):
    passed: bool
    mode: str   # "repair" | "observer"
    reason: str


def check(result: ClassifierResult) -> GateDecision:
    """
    Evaluate classifier confidence against threshold.

    Args:
        result: ClassifierResult from regex_pass.classify()

    Returns:
        GateDecision — passed=True (repair mode) or passed=False (observer mode).
    """
    if result.confidence >= CONFIDENCE_THRESHOLD:
        decision = GateDecision(
            passed=True,
            mode="repair",
            reason=f"confidence {result.confidence:.2f} >= {CONFIDENCE_THRESHOLD}",
        )
    else:
        decision = GateDecision(
            passed=False,
            mode="observer",
            reason=f"confidence {result.confidence:.2f} < {CONFIDENCE_THRESHOLD} — observer mode",
        )

    log.info(
        "safety_gate.decision",
        passed=decision.passed,
        mode=decision.mode,
        confidence=result.confidence,
        category=result.category,
    )

    return decision


if __name__ == "__main__":
    # High confidence — should pass
    high = ClassifierResult(
        category="DependencyError",
        confidence=0.99,
        matched_pattern=r"ModuleNotFoundError",
        keyword="pkg_resources",
        affected_file="requirements.txt",
        bug_signature="smoke/test:DependencyError:pkg_resources:requirements.txt",
    )
    d = check(high)
    assert d.passed is True and d.mode == "repair", f"Expected repair, got {d}"
    print(f"PASS  high confidence: mode={d.mode}")

    # Low confidence — should block
    low = ClassifierResult(
        category="DependencyError",
        confidence=0.50,
        matched_pattern=r"setuptools",
        keyword="setuptools",
        affected_file="requirements.txt",
        bug_signature="smoke/test:DependencyError:setuptools:requirements.txt",
    )
    d = check(low)
    assert d.passed is False and d.mode == "observer", f"Expected observer, got {d}"
    print(f"PASS  low confidence: mode={d.mode}")

    print("safety_gate smoke test PASSED")
