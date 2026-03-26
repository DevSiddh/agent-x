# Agent-X v3.0 | Open Questions & Known Gaps
# Last updated: 2026-03-26
# AUTHORITATIVE list — check here before adding to session_prompts.md

---

## Q1 — registry.jsonl has no status update mechanism ✅ FIXED 2026-03-26
- update_registry_status() added to project_context.py
- Orchestrator calls it with "completed" when is_done() = True

## Q2 — post_task_comment not called on task FAILURE ✅ FIXED 2026-03-26 (session-2)
- post_task_comment(status="failed") wired in best_of_n_exhausted path

## Q3 — .agent/context.md not committed to GitHub after task ✅ FIXED 2026-03-26
- _commit_context() called unconditionally after every successful task (removed github_repo guard)
- git add + commit always; push only if remote configured (git remote check)
- 6 tests: TestCommitContext (commits/skips/no-raise/no-remote) + TestRunOnceCommitContext (always called)

## Q4 — Orchestrator deepseek_call placeholder not implemented ✅ FIXED 2026-03-26 (session-3)
- _execute_file_ops now calls DeepSeek via _call_deepseek()
- AGENT_X_STATIC_PROMPT + AcceptanceCriteria + hint wired

## Q5 — hint field not injected into Orchestrator prompt ✅ FIXED 2026-03-26 (session-3)
- _build_agent_x_prompt() injects task.hint when set
