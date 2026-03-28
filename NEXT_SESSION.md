# NEXT_SESSION — read this first, skip BRIEFING.md unless unclear
# Updated: 2026-03-28

Step:     FIX-2
Files:    phase3/orchestrator.py → _run_tests()
Read:     docs/prompts/v41_creation_fixes.md → FIX-2 section only
Note:     FIX-2 = uv pip install -r requirements.txt before pytest + -x --ff flags + TEST_TIMEOUT_FILE/FULL env vars
Branch:   agent-x/fix-step0
Tests:    python -m pytest tests/ -q  (657 must pass before touching anything)

Last session (2026-03-28):
  - FIX-1 DONE — _run_ast_mapper per-file (_extract_signatures), global_interfaces injected,
    SkillVault wired (find_relevant + sample_top + used_skill_ids tracked)
  - 657 tests passing

Queue after FIX-2:
  FIX-3 → FIX-4 → FIX-5 → FIX-6 → FIX-7 → FIX-8 → FIX-9
  Full spec for each → docs/prompts/v41_creation_fixes.md

If unclear: read docs/BRIEFING.md for full picture.
