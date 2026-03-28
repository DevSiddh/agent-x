# NEXT_SESSION — read this first, skip BRIEFING.md unless unclear
# Updated: 2026-03-28

Step:     ALL TIER 1-3 FIXES COMPLETE (FIX-1 through FIX-9)
Next:     FIX-17 → dynamic test generation (TIER 4, gated after FIX-3+FIX-9)
          OR run a harder smoke test (FastAPI project) to validate full pipeline
Read:     docs/prompts/v41_creation_fixes.md → FIX-17 section
Branch:   agent-x/fix-step0
Tests:    python -m pytest tests/ -q  (657 must pass)
Branch:   agent-x/fix-step0
Tests:    python -m pytest tests/ -q  (657 must pass before touching anything)

Last session (2026-03-28):
  - FIX-1 DONE — _run_ast_mapper per-file (_extract_signatures), global_interfaces injected,
    SkillVault wired (find_relevant + sample_top + used_skill_ids tracked)
  - FIX-2 DONE — _run_tests(): uv/pip install before pytest, -x --ff flags,
    skip full suite when no test file, TEST_TIMEOUT_FILE/FULL env vars added
  - FIX-3 DONE — _execute_scaffold() added, SCAFFOLD branch in _execute_file_ops(),
    CREATION_SYSTEM_PROMPT updated with T0 rule + topological order + example
  - FIX-4 DONE — REQUIREMENTS RULE added to CREATION_SYSTEM_PROMPT: T1=requirements.txt
    always after T0, packages inferred from goal, example updated to T0→T1→T2
  - SCHEMA FIX — AcceptanceCriteria min_length relaxed to 0, Task validator enforces
    min 3 cases for impl tasks only (scaffold+requirements exempt)
  - AUDIT PASSED — smoke-calc: T0 scaffold ✓ T1 requirements ✓ T2 impl ✓ 3 tests pass
  - FIX-5 DONE — plan_goal() now accepts existing_context param, run_loop() passes
    read_context(repo_path) on resume, Agent-Y gets "what's already built" block
  - FIX-7 DONE — FILE_EDIT fixed: DeepSeek returns full new content → _make_unified_diff()
    generates diff via difflib → apply_patch() applies it. Empty diff = no-op (not error).
  - FIX-8 DONE — _safe_repo_path() wraps ALL file_str constructions in _execute_file_ops()
    and _execute_scaffold() — path traversal blocked at every entry point
  - FIX-9 DONE — 3 gates before write_file():
    Gate 1: _is_placeholder() — catches TODO/pass stubs, rejects with correct reason
    Gate 2: _has_syntax_error() — ast.parse before pytest boots, zero cost
    Gate 3: _check_imports() — validates imports against global_interfaces (task 2+)
  - FIX-6 DONE — replan() now fires correctly:
    * run_once() streak==2 path just marks failed (no longer returns early)
    * _execute_file_ops() returns (bool, last_content) tuple — content stored in state.last_failed_diff
    * run_loop() detects streak==2 after run_once(), calls replan() with failed content,
      replaces pending tasks with surgical sub-tasks, resets streak to 0
    * SharedState gains last_failed_diff field
    * 3 test mocks updated for tuple return
  - 657 tests passing

Queue after FIX-2:
  FIX-3 → FIX-4 → FIX-5 → FIX-6 → FIX-7 → FIX-8 → FIX-9
  Full spec for each → docs/prompts/v41_creation_fixes.md

If unclear: read docs/BRIEFING.md for full picture.
