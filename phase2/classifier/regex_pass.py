"""
phase2/classifier/regex_pass.py
Regex-based classifier — identifies failure category, keyword, affected file,
and confidence score from cleaned error lines.
"""

import re
from typing import NamedTuple

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Pattern registry — (compiled_regex, keyword, weight)
# Weight contributes to confidence. Multiple matches accumulate (cap 0.99).
# ---------------------------------------------------------------------------

class _Pattern(NamedTuple):
    regex: re.Pattern[str]
    keyword: str
    weight: float


_PATTERNS: dict[str, list[_Pattern]] = {
    "DependencyError": [
        _Pattern(re.compile(r"ModuleNotFoundError: No module named", re.I), "ModuleNotFoundError", 0.70),
        _Pattern(re.compile(r"No module named '?(\S+?)'?", re.I), "ModuleNotFoundError", 0.30),
        _Pattern(re.compile(r"pkg_resources", re.I), "pkg_resources", 0.30),
        _Pattern(re.compile(r"Could not find a version that satisfies the requirement (\S+)", re.I), "pip_conflict", 0.50),
        _Pattern(re.compile(r"setuptools", re.I), "setuptools", 0.20),
    ],
    "EnvironmentError": [
        _Pattern(re.compile(r"no.build.isolation", re.I), "no_build_isolation", 0.90),
        _Pattern(re.compile(r"stale __pycache__", re.I), "stale_pycache", 0.90),
        _Pattern(re.compile(r"ImportError.*circular import", re.I), "stale_pycache", 0.50),
        _Pattern(re.compile(r"pip install failed", re.I), "pip_failed", 0.30),
        _Pattern(re.compile(r"port.*already in use|address already in use", re.I), "port_conflict", 0.80),
        _Pattern(re.compile(r"environment variable.*not set", re.I), "missing_env_var", 0.70),
        _Pattern(re.compile(r"EnvironmentError", re.I), "missing_env_var", 0.20),
    ],
    "ConfigError": [
        _Pattern(re.compile(r"no such table:\s*(\w+)", re.I), "no_such_table", 0.80),
        _Pattern(re.compile(r"OperationalError.*no such table", re.I), "no_such_table", 0.70),
        _Pattern(re.compile(r"OperationalError", re.I), "db_error", 0.30),
        _Pattern(re.compile(r"malformed YAML|yaml.*error", re.I), "malformed_yaml", 0.80),
        _Pattern(re.compile(r"yaml\.YAMLError|YAMLError", re.I), "malformed_yaml", 0.20),
        _Pattern(re.compile(r"KeyError: '([^']+)'", re.I), "missing_key", 0.50),
    ],
    "RuntimeError": [
        _Pattern(re.compile(r"Field.*conflicts with protected namespace", re.I), "pydantic_namespace", 0.80),
        _Pattern(re.compile(r"protected.namespace.*model_", re.I), "pydantic_namespace", 0.70),
        _Pattern(re.compile(r"PydanticUserError", re.I), "pydantic_error", 0.60),
        _Pattern(re.compile(r"AssertionError", re.I), "assertion_error", 0.90),
        _Pattern(re.compile(r"assert.*failed|assertion failed", re.I), "assertion_error", 0.70),
        _Pattern(re.compile(r"TypeError", re.I), "type_error", 0.50),
        _Pattern(re.compile(r"TypeError:.*argument", re.I), "type_error", 0.40),
        _Pattern(re.compile(r"ValueError", re.I), "value_error", 0.40),
        _Pattern(re.compile(r"AttributeError", re.I), "attribute_error", 0.40),
    ],
    "BuildError": [
        _Pattern(re.compile(r"docker.*failed|failed to build image", re.I), "docker_failure", 0.80),
        _Pattern(re.compile(r"build isolation", re.I), "build_isolation", 0.50),
    ],
}

FAILURE_CATEGORIES = list(_PATTERNS.keys())


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

class ClassifierResult(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    matched_pattern: str
    keyword: str
    affected_file: str
    bug_signature: str  # format: repo:ErrorType:keyword:file  (P12)


# ---------------------------------------------------------------------------
# File extraction
# ---------------------------------------------------------------------------

def _extract_affected_file(
    error_lines: list[str], category: str, keyword: str
) -> str:
    """Extract affected file from traceback, fall back to category heuristics."""
    for line in error_lines:
        m = re.search(r'File "([^"]+)"', line)
        if m:
            return m.group(1)

    # Heuristics when no traceback file reference found
    if keyword == "no_build_isolation":
        return "Makefile"
    if keyword == "stale_pycache":
        return "scripts/restart.sh"
    if category == "DependencyError":
        return "requirements.txt"

    return "unknown"


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify(error_lines: list[str], repo: str) -> ClassifierResult:
    """
    Classify error lines into a failure category with confidence score.

    Args:
        error_lines: Cleaned log lines from LogParser.
        repo:        Repository identifier (used in bug_signature, P12).

    Returns:
        ClassifierResult with category, confidence, keyword, file, signature.
    """
    full_text = "\n".join(error_lines)

    best_category = "DependencyError"
    best_score = 0.0
    best_keyword = "unknown"
    best_pattern_str = ""

    for category, patterns in _PATTERNS.items():
        score = 0.0
        first_keyword = ""
        first_pattern = ""

        for pat in patterns:
            if pat.regex.search(full_text):
                score += pat.weight
                if not first_keyword:
                    first_keyword = pat.keyword
                    first_pattern = pat.regex.pattern

        if score > best_score:
            best_score = score
            best_category = category
            best_keyword = first_keyword
            best_pattern_str = first_pattern

    confidence = min(0.99, best_score)
    affected_file = _extract_affected_file(error_lines, best_category, best_keyword)
    bug_signature = f"{repo}:{best_category}:{best_keyword}:{affected_file}"

    result = ClassifierResult(
        category=best_category,
        confidence=confidence,
        matched_pattern=best_pattern_str,
        keyword=best_keyword,
        affected_file=affected_file,
        bug_signature=bug_signature,
    )

    log.info(
        "classifier.result",
        category=result.category,
        confidence=result.confidence,
        keyword=result.keyword,
        affected_file=result.affected_file,
        repo=repo,
    )

    return result


def classify_with_fallback(
    error_lines: list[str],
    repo: str,
) -> ClassifierResult:
    """
    Two-pass classifier chain:
      Pass 1: regex classify() — always runs, $0, microseconds, deterministic
      Pass 2: EmbeddingClassifier.classify() — only if regex confidence < 0.85

    Returns ClassifierResult from whichever pass succeeds.
    Falls through to original low-confidence result if embedding also fails.
    Never raises.
    """
    result = classify(error_lines, repo=repo)
    if result.confidence >= 0.85:
        return result  # regex passed — fast path, no embedding needed

    log.info(
        "classifier.regex_miss",
        confidence=result.confidence,
        triggering_semantic_fallback=True,
    )
    try:
        from phase2.classifier.semantic_fallback import EmbeddingClassifier
        engine = EmbeddingClassifier()
        semantic_result = engine.classify(error_lines, repo=repo)
        if semantic_result is not None:
            log.info(
                "classifier.semantic_hit",
                category=semantic_result.category,
                confidence=semantic_result.confidence,
            )
            return semantic_result
    except Exception as exc:
        log.warning("classifier.semantic_error", error=str(exc))

    # Both passes failed — return original low-confidence result.
    # PreSafetyGate will catch it and set observer mode.
    return result


if __name__ == "__main__":
    # Smoke test — classify all 5 synthetic cases
    import json
    from pathlib import Path

    jsonl = Path(__file__).resolve().parents[2] / "phase1" / "dataset" / "synthetic.jsonl"
    with open(jsonl) as f:
        cases = [json.loads(l) for l in f if l.strip()]

    print("=== Classifier Smoke Test ===")
    all_ok = True
    for case in cases:
        result = classify(case["error_log"], repo="smoke/test")
        ok = result.category == case["failure_category"]
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(
            f"  {status}  {case['id']} | expected={case['failure_category']} "
            f"got={result.category} conf={result.confidence:.2f} "
            f"keyword={result.keyword}"
        )

    print("PASSED" if all_ok else "FAILED — see above")
