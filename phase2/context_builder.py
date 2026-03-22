"""
phase2/context_builder.py
v2.1 ContextBuilder — enriches DeepSeek prompt with:
  1. Affected file content (spike proved LLM cannot patch blind)
  2. Up to 3 past similar fixes from MemoryEngine.find_for_rag() (triple-hybrid RAG)
  3. Error summary header

Replaces the inline _build_context() helper in pipeline.py.
"""

from pathlib import Path

import structlog

try:
    from phase2.classifier.regex_pass import ClassifierResult
    from phase2.memory.similarity import MemoryEngine, _RAG_HIGH_THRESHOLD
    from phase2.tools.github_file import extract_relative_path, fetch_file
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from phase2.classifier.regex_pass import ClassifierResult
    from phase2.memory.similarity import MemoryEngine, _RAG_HIGH_THRESHOLD
    from phase2.tools.github_file import extract_relative_path, fetch_file

log = structlog.get_logger()


def _action_tag(score: float) -> str:
    """Map hybrid score to action-oriented tag for Agent-Y context header."""
    if score >= _RAG_HIGH_THRESHOLD:
        return "[HIGH RELEVANCE: Adapt this pattern]"
    return "[LOW RELEVANCE: Loose inspiration only. DO NOT copy directly.]"


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
        # P23 fix: affected_file may be a GitHub Actions runner absolute path.
        # Try to extract repo-relative path and fetch from GitHub API.
        file_content: str | None = None
        rel_path = extract_relative_path(affected)
        if rel_path:
            # repo is first segment of bug_signature: "owner/repo:Category:kw:file"
            sig_parts = classifier_result.bug_signature.split(":", 1)
            repo = sig_parts[0] if sig_parts else ""
            if repo:
                file_content = fetch_file(repo, rel_path)
                if file_content is not None:
                    log.info(
                        "context_builder.file_fetched_github",
                        file=rel_path,
                        repo=repo,
                    )

        if file_content is not None:
            sections.append(
                f"## Affected File: {rel_path}\n```\n{file_content}\n```"
            )
        else:
            sections.append(
                f"## Affected File: {affected}\n# File not found in fixture"
            )
            log.warning("context_builder.file_missing", file=affected)

    # --- Section 3: Past similar fixes (triple-hybrid RAG) -----------------
    engine = MemoryEngine()
    rag_results: list[tuple[dict, float]] = engine.find_for_rag(
        category=classifier_result.category,
        matched_pattern=classifier_result.matched_pattern,
        keyword=classifier_result.keyword,
        affected_file=classifier_result.affected_file,
        bug_signature=classifier_result.bug_signature,
    )

    if rag_results:
        past_fixes: list[str] = []
        for i, (entry_dict, score) in enumerate(rag_results, 1):
            tag = _action_tag(score)
            patch_preview = (entry_dict.get("patch_applied") or "").strip()
            if len(patch_preview) > 500:
                patch_preview = patch_preview[:500] + "\n... (truncated)"
            past_fixes.append(
                f"### Past Fix {i} {tag} "
                f"(decision={entry_dict.get('decision')}, "
                f"retries={entry_dict.get('retries_used', 0)})\n"
                f"```diff\n{patch_preview}\n```"
            )
        sections.append("## Past Similar Fixes\n" + "\n\n".join(past_fixes))
        log.info("context_builder.rag_hits", count=len(rag_results))
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
