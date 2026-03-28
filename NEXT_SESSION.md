# NEXT_SESSION — read this first, skip BRIEFING.md unless unclear
# Updated: 2026-03-28

Step:     FIX-8
Files:    phase3/orchestrator.py → _execute_file_ops() — audit every path construction
Read:     docs/prompts/v41_creation_fixes.md → FIX-8 section only
Note:     FIX-8 = resolve_safe_path() missing on some writes — security audit + targeted additions
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
