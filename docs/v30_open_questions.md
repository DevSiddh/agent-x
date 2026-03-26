# Agent-X v3.0 | Open Questions & Known Gaps
# Last updated: 2026-03-26
# AUTHORITATIVE list — check here before adding to session_prompts.md

---

## Q1 — registry.jsonl has no status update mechanism
- Status stays "active" forever — no "completed" or "deleted" transition
- Fix: add update_registry_status() to project_context.py
- Gate: build when PROJECT DELETE (v3.2 Telegram /delete) is implemented

## Q2 — post_task_comment not called on task FAILURE
- Success path narrates to PR. Failure path is silent.
- Fix: call post_task_comment with status="failed" in mark_failed path
- Gate: low priority — nice-to-have for v4.1

## Q3 — .agent/context.md not committed to GitHub after task
- Orchestrator writes context locally but doesn't git commit + push it
- CLAUDE.md spec: "Code + .agent/context.md committed together after every task"
- Fix: add git commit + push in orchestrator post-task flow
- Gate: needs GITHUB_TOKEN in state or env — already available

## Q4 — Orchestrator deepseek_call placeholder not implemented
- write_file generates `# {file_str}` placeholder, not real DeepSeek content
- Real impl needs AGENT_X_STATIC_PROMPT + DeepSeek call
- Gate: core v4.1 work — this IS the v4.1 step

## Q5 — hint field added to Task but not injected into Orchestrator prompt
- Task.hint exists in schema but orchestrator never reads it
- Fix: add hint injection in _execute_file_ops when building DeepSeek prompt
- Gate: v4.1 — same session as Q4
