# NEXT_SESSION — read this first, skip BRIEFING.md unless unclear
# Updated: 2026-03-28

Step:     FIX-17 or FIX-18 (TIER 4)
Files:    See docs/prompts/v41_creation_fixes.md → FIX-17 or FIX-18
Read:     FIX-17 = dynamic test generation (TEST_FRAMEWORK_MAP + conftest.py per project_type)
          FIX-18 = agentic RAG for creation mode (creation_context_builder.py)
Branch:   agent-x/fix-step0
Tests:    python -m pytest tests/ -q  (657 must pass)

Last session (2026-03-28) — ALL TIER 1-3 COMPLETE:
  - FIX-1 DONE — _run_ast_mapper per-file, global_interfaces injected, SkillVault wired
  - FIX-2 DONE — pip install before pytest, -x --ff flags, TEST_TIMEOUT_FILE/FULL
  - FIX-3 DONE — _execute_scaffold() + SCAFFOLD branch + T0 rule in CREATION_SYSTEM_PROMPT
  - FIX-4 DONE — REQUIREMENTS RULE: T1=requirements.txt always in plan
  - SCHEMA FIX — AcceptanceCriteria min_length relaxed, Task validator enforces min 3 for impl
  - FIX-5 DONE — plan_goal() reads context.md on resume via existing_context param
  - FIX-6 DONE — replan() fires: streak==2 triggers replan in run_loop, last_failed_diff captured
  - FIX-7 DONE — FILE_EDIT via difflib not raw LLM text
  - FIX-8 DONE — _safe_repo_path() on all writes + scaffold
  - FIX-9 DONE — 3 pre-write gates: placeholder / syntax / import validation
  - AUDIT v1 PASSED — smoke-calc: 3/3 tests pass
  - AUDIT v2 PASSED — FastAPI todo API: T0 scaffold ✓ T1 requirements(4 pkgs) ✓ T2 impl ✓ 3/3 tests pass
  - Prompt fixes: AGENT_X_STATIC_PROMPT FastAPI route hints, POST status_code=201,
    requirements.txt special-case prompt, CREATION_SYSTEM_PROMPT FastAPI rules tightened
  - global_interfaces captured: [test_todo_api.py, todo_api.py] — FIX-1 confirmed working
  - 657 tests passing
