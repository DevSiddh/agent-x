"""
phase2/patch_gen/sanitiser.py
Two-layer defence against LLM returning markdown instead of raw unified diff (P3).
Layer 1: system prompt (enforced in worker.py)
Layer 2: this module strips fences + validates before git apply
"""

import re

import structlog
from pydantic import BaseModel

log = structlog.get_logger()

MAX_DIFF_LINES = 15


class SanitiserResult(BaseModel):
    passed: bool
    diff: str
    line_count: int
    rejection_reason: str


def strip_markdown_fences(text: str) -> str:
    """
    Remove markdown code fences and return only the unified diff portion.
    Finds the first line starting with '---' and returns from there. (P3)
    """
    # Strip leading/trailing whitespace
    text = text.strip()

    # Remove code fence opening lines (```diff, ```patch, ``` etc.)
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.MULTILINE)
    # Remove code fence closing lines
    text = re.sub(r"^```\s*$", "", text, flags=re.MULTILINE)

    # Find the first line starting with --- (unified diff header)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("---"):
            return "\n".join(lines[i:]).strip()

    # No diff header found — return stripped text as-is
    return text.strip()


def count_diff_lines(diff: str) -> int:
    """
    Count only actual changed lines (+ or -), excluding +++ and --- headers.
    """
    count = 0
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            count += 1
        elif line.startswith("-") and not line.startswith("---"):
            count += 1
    return count


def validate_patch(diff: str) -> SanitiserResult:
    """
    Validate a diff string for git apply compatibility.

    Rejects if:
    - diff doesn't start with ---
    - line_count > MAX_DIFF_LINES (15)

    Returns SanitiserResult with passed, diff, line_count, rejection_reason.
    """
    cleaned = strip_markdown_fences(diff)
    line_count = count_diff_lines(cleaned)

    if not cleaned.startswith("---"):
        reason = "diff does not start with --- (not a valid unified diff)"
        log.warning("sanitiser.rejected", reason=reason, line_count=line_count)
        return SanitiserResult(
            passed=False,
            diff=cleaned,
            line_count=line_count,
            rejection_reason=reason,
        )

    if line_count > MAX_DIFF_LINES:
        reason = f"patch too large: {line_count} lines (max {MAX_DIFF_LINES})"
        log.warning("sanitiser.rejected", reason=reason, line_count=line_count)
        return SanitiserResult(
            passed=False,
            diff=cleaned,
            line_count=line_count,
            rejection_reason=reason,
        )

    log.info("sanitiser.accepted", line_count=line_count)
    return SanitiserResult(
        passed=True,
        diff=cleaned,
        line_count=line_count,
        rejection_reason="",
    )


if __name__ == "__main__":
    # Smoke tests
    fenced = "```diff\n--- a/foo.txt\n+++ b/foo.txt\n@@ -1 +1 @@\n-old\n+new\n```"
    result = strip_markdown_fences(fenced)
    assert result.startswith("---"), f"strip failed: {result!r}"
    print("PASS  strip_markdown_fences removes fences")

    clean_diff = "--- a/foo.txt\n+++ b/foo.txt\n@@ -1 +1 @@\n-old\n+new"
    result = strip_markdown_fences(clean_diff)
    assert result == clean_diff, f"clean diff should be unchanged: {result!r}"
    print("PASS  strip_markdown_fences handles already-clean diff")

    assert count_diff_lines(clean_diff) == 2
    print("PASS  count_diff_lines counts 2 (+new, -old)")

    r = validate_patch(clean_diff)
    assert r.passed is True and r.line_count == 2
    print("PASS  validate_patch accepts valid diff")

    r = validate_patch("not a diff at all")
    assert r.passed is False
    print("PASS  validate_patch rejects non-diff text")

    big = "--- a/f\n+++ b/f\n@@ -1 +1 @@\n" + "\n".join(f"+line{i}" for i in range(20))
    r = validate_patch(big)
    assert r.passed is False and r.line_count == 20
    print("PASS  validate_patch rejects > 15 lines")

    print("sanitiser.py smoke test PASSED")
