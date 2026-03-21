"""
phase2/context_builder.py
v1.1 ContextBuilder — enriches DeepSeek prompt with:
  1. Affected file content (spike proved LLM cannot patch blind)
  2. Up to 3 past similar fixes from memory store (RAG retrieval)
  3. Error summary header

Replaces the inline _build_context() helper in pipeline.py.
"""

from pathlib import Path

import structlog

try:
    from phase2.classifier.regex_pass import ClassifierResult
    from phase2.memory.store import MemoryEntry, get_similar
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from phase2.classifier.regex_pass import ClassifierResult
    from phase2.memory.store import MemoryEntry, get_similar

log = structlog.get_logger()


def build_context(
    classifier_result: ClassifierResult,
    fixture_path: Path,
    error_lines: list[str] | None = None,
) -> str:
    """
    Build enriched context string for the DeepSeek patch prompt.

    Args:
        classifier_result: Output of RegexClassifier.
        fixture_path:      Path to the fixture git repo.
        error_lines:       Cleaned error lines from LogParser (optional, for summary).

    Returns:
        Multi-section context string ready to insert into the LLM user prompt.
    """
    sections: list[str] = []

    # --- Section 1: Error summary -----------------------------------------
    summary_lines = error_lines or []
    summary = "\n".join(summary_lines[:20])  # cap at 20 lines for token budget
    sections.append(
        f"## Error Summary\n"
        f"Category : {classifier_result.category}\n"
        f"Keyword  : {classifier_result.keyword}\n"
        f"File     : {classifier_result.affected_file}\n"
        f"Signature: {classifier_result.bug_signature}\n"
        f"\n```\n{summary}\n```"
    )

    # --- Section 2: Affected file content ----------------------------------
    affected = classifier_result.affected_file
    file_path = fixture_path / affected

    if file_path.exists():
        file_content = file_path.read_text(encoding="utf-8")
        sections.append(
            f"## Affected File: {affected}\n```\n{file_content}\n```"
        )
        log.info("context_builder.file_loaded", file=affected)
    else:
        sections.append(f"## Affected File: {affected}\n# File not found in fixture")
        log.warning("context_builder.file_missing", file=affected)

    # --- Section 3: Past similar fixes (RAG) -------------------------------
    similar: list[MemoryEntry] = get_similar(classifier_result.bug_signature, limit=5)

    if similar:
        past_fixes: list[str] = []
        for i, entry in enumerate(similar, 1):
            patch_preview = (entry.patch_applied or "").strip()
            if len(patch_preview) > 500:
                patch_preview = patch_preview[:500] + "\n... (truncated)"
            past_fixes.append(
                f"### Past Fix {i} (decision={entry.decision}, "
                f"retries={entry.retries_used})\n"
                f"```diff\n{patch_preview}\n```"
            )
        sections.append("## Past Similar Fixes\n" + "\n\n".join(past_fixes))
        log.info("context_builder.rag_hits", count=len(similar))
    else:
        log.info("context_builder.rag_empty", signature=classifier_result.bug_signature)

    return "\n\n".join(sections)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    from phase2.classifier.regex_pass import ClassifierResult

    result = ClassifierResult(
        category="DependencyError",
        confidence=0.99,
        matched_pattern="ModuleNotFoundError",
        keyword="pkg_resources",
        affected_file="requirements.txt",
        bug_signature="synthetic:DependencyError:pkg_resources:requirements.txt",
    )

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "syn_001"
    ctx = build_context(
        classifier_result=result,
        fixture_path=fixture,
        error_lines=["ModuleNotFoundError: No module named 'pkg_resources'"],
    )

    assert "## Error Summary" in ctx
    assert "## Affected File" in ctx
    assert "DependencyError" in ctx
    print("context_builder smoke test PASSED")
    print(f"\n--- context preview ({len(ctx)} chars) ---")
    print(ctx[:400])
