# NEXT_SESSION — read this first, skip BRIEFING.md unless unclear
# Updated: 2026-03-28

Step:     FIX-1
Files:    phase3/orchestrator.py → _run_ast_mapper() + _build_agent_x_prompt()
Read:     docs/prompts/v41_creation_fixes.md → FIX-1 section only
Note:     FIX-1 now covers 3 gaps: per-file AST scope + global_interfaces injection + SkillVault wiring
Branch:   agent-x/fix-step0
Tests:    python -m pytest tests/ -q  (657 must pass before touching anything)

Last session (2026-03-28):
  - FIX-19 (Surgical Pytest) merged into FIX-2 spec — no separate entry
  - FIX-2 now: pip install + -x --ff + timeout tiers in _run_tests()
  - NEXT_SESSION.md created as fast-path session start

Queue after FIX-1:
  FIX-2 → FIX-3 → FIX-4 → FIX-5 → FIX-6 → FIX-7 → FIX-8 → FIX-9
  Full spec for each → docs/prompts/v41_creation_fixes.md

If unclear: read docs/BRIEFING.md for full picture.
