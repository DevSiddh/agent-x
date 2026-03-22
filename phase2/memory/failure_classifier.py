"""
phase2/memory/failure_classifier.py — Step E1

Read all rejected entries from memory.jsonl → classify WHY they were rejected
→ output a pattern report so you know which part of the pipeline to improve.

TWO-PATH classification:
  Path 1 — rejection_reason already set (new entries, post-E1):
    use the field directly if it's a valid category
  Path 2 — rejection_reason == "" (old entries, pre-E1):
    classify from entry["error"] field via regex

Usage:
    python phase2/memory/failure_classifier.py
"""

import json
import re
import sys
from pathlib import Path

import structlog
from pydantic import BaseModel

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "logic_issue",
    "security_issue",
    "prompt_issue",
    "size_issue",
    "context_issue",
    "flaky",
}

# (category, [patterns]) — first match wins
_REGEX_RULES: list[tuple[str, list[str]]] = [
    ("prompt_issue",  [r"diff header missing", r"\+\+\+ header", r"missing ---",
                       r"no unified diff", r"SyntaxError", r"invalid syntax",
                       r"git apply", r"patch.*fail", r"corrupt patch",
                       r"patch fragment", r"patch does not apply"]),
    ("context_issue", [r"wrong file path", r"file not found", r"path mismatch",
                       r"affected_file", r"no such file"]),
    ("logic_issue",   [r"tests still fail", r"regression", r"new failures",
                       r"test_failure", r"assert", r"FAILED"]),
    ("size_issue",    [r"exceeds", r"too many lines", r"15 lines", r"line count",
                       r"line_count"]),
    ("security_issue",[r"hardcoded secret", r"CVE-", r"vulnerability", r"bandit"]),
    ("flaky",         [r"flaky"]),
]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class RejectionSummary(BaseModel):
    total_rejected: int
    by_category: dict[str, int]
    by_category_pct: dict[str, float]
    unknown_reasons: list[str]
    top_issue: str
    recommendation: str


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

_RECOMMENDATIONS: dict[str, str] = {
    "prompt_issue":   "Harden system prompt — add explicit diff format example with --- a/ +++ b/ header",
    "context_issue":  "Fix context_builder file resolution — ensure affected_file path is correct before LLM call",
    "logic_issue":    "Improve Agent-Y strategy or raise retry count — patch applies but logic is wrong",
    "size_issue":     "Narrow prompt scope — instruct LLM to use simpler, smaller fix under 15 lines",
    "security_issue": "Add explicit 'no hardcoded values' to system prompt — bandit rejecting patched code",
    "flaky":          "Add retry logic with test stabilisation — tests are non-deterministic",
    "unknown":        "Review unknown_reasons list manually — no pattern matched these rejection messages",
}


def _classify_from_text(text: str) -> str:
    """Apply regex rules to raw error text. Returns category string."""
    for category, patterns in _REGEX_RULES:
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return category
    return "unknown"


def classify_rejections(memory_path: Path) -> RejectionSummary:
    """
    Read memory.jsonl → filter decision == "rejected" → classify each entry.

    Path 1: rejection_reason in VALID_CATEGORIES → use directly.
    Path 2: rejection_reason == "" → classify from error field via regex.

    Never raises. Returns RejectionSummary with zeros if file missing.
    """
    counts: dict[str, int] = {cat: 0 for cat in VALID_CATEGORIES}
    counts["unknown"] = 0
    unknown_reasons: list[str] = []
    total_rejected = 0

    if not memory_path.exists():
        return _build_summary(counts, unknown_reasons, total_rejected)

    try:
        with open(memory_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("decision") != "rejected":
                    continue

                total_rejected += 1
                rejection_reason: str = entry.get("rejection_reason", "")

                # Path 1 — reason already classified
                if rejection_reason in VALID_CATEGORIES:
                    counts[rejection_reason] = counts.get(rejection_reason, 0) + 1
                    continue

                # Path 2 — classify from error field
                error_text = entry.get("error", "") or rejection_reason
                category = _classify_from_text(error_text)
                counts[category] = counts.get(category, 0) + 1

                if category == "unknown" and error_text:
                    unknown_reasons.append(error_text[:200])

    except Exception as exc:
        log.error("failure_classifier.read_error", error=str(exc))

    return _build_summary(counts, unknown_reasons, total_rejected)


def _build_summary(
    counts: dict[str, int],
    unknown_reasons: list[str],
    total_rejected: int,
) -> RejectionSummary:
    by_category_pct: dict[str, float] = {}
    for cat, n in counts.items():
        by_category_pct[cat] = round((n / total_rejected * 100) if total_rejected else 0.0, 1)

    top_issue = max(counts, key=lambda c: counts[c]) if any(counts.values()) else "unknown"
    recommendation = _RECOMMENDATIONS.get(top_issue, _RECOMMENDATIONS["unknown"])

    return RejectionSummary(
        total_rejected=total_rejected,
        by_category=dict(counts),
        by_category_pct=by_category_pct,
        unknown_reasons=unknown_reasons,
        top_issue=top_issue,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def print_report(summary: RejectionSummary) -> None:
    """Print human-readable rejection analysis to stdout."""
    print("\n=== Rejection Analysis ===")
    print(f"Total rejected : {summary.total_rejected}")
    if summary.total_rejected == 0:
        print("No rejections found in memory.jsonl.")
        return

    print(f"Top issue      : {summary.top_issue} ({summary.by_category_pct.get(summary.top_issue, 0)}%)")
    print(f"Recommendation : {summary.recommendation}")
    print()
    print("Breakdown:")
    for cat, n in sorted(summary.by_category.items(), key=lambda x: -x[1]):
        if n > 0:
            pct = summary.by_category_pct.get(cat, 0)
            print(f"  {cat:<20} {n:>4}  ({pct}%)")

    if summary.unknown_reasons:
        print(f"\nUnknown reasons ({len(summary.unknown_reasons)}):")
        for r in summary.unknown_reasons[:5]:
            print(f"  - {r}")
        if len(summary.unknown_reasons) > 5:
            print(f"  ... and {len(summary.unknown_reasons) - 5} more")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    memory_path = Path(__file__).resolve().parents[2] / "memory" / "memory.jsonl"
    summary = classify_rejections(memory_path)
    print_report(summary)
    print("failure_classifier.py smoke test PASSED")
