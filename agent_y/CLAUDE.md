# CLAUDE.md — Agent-Y v1
# Reasoning layer for Agent-X. Lives in agent_y/ — same repo, same pipeline.
# Last updated: 2026-03-20

## GIT RULES
- Contributor: CH Y SAI SIDDHARDHA only — Claude NEVER commits or pushes
- Branch: agent-x/fix-agent-y-<step> — never main
- No commit until ALL tests for that step pass
- Commit format: [agent-y-AN] description of what was built

## FIRST COMMAND EVERY SESSION
  python scripts/verify_env.py
  Fails → fix before touching anything

## SESSION START
1. Read @docs/progress.md → Agent-Y section → find current PENDING step
2. Read @docs/session_prompts.md → step AN → execute fully
3. Update docs/progress.md after every completed file → STOP

## Hard Rules (no exceptions)
1. Reasoner NEVER generates code — reasoning + strategy ONLY
2. files_to_change ALWAYS ≤ 3 items
3. Validate JSON schema keys after json.loads (not just parse success)
4. validate_strategy() MUST run before returning ReasonerOutput (P1)
5. ReasonerError → pipeline continues with raw context — NEVER blocks (P5)
6. confidence is metadata ONLY — never used for safety gate or decisions (P3)
7. Max 2 retries — retry prompt MUST include parse error message + required keys
8. After 2 retries → raise ReasonerError (graceful degrade, not crash)
9. DEEPSEEK_API_KEY read lazily inside function — never at module level
10. No cross-imports from phase1/ or phase2/ internals — use public interfaces only

## Pipeline Position (locked)
...→ ContextBuilder → agent_y.Reasoner → DeepSeekWorker →...
Reasoner is OPTIONAL — pipeline works without it (fallback path required)

## v1 Done Condition
agent_y/reasoner.py + tests → all pass
phase2/pipeline.py wired → all 5 synthetic cases still accepted
ReasonerError fallback path tested and confirmed working

## Upgrade Queue (locked until v1 ships)
v1.1 → local model reasoning (Ollama + Qwen2.5-7B, zero API cost)
v1.2 → multi-step reasoning chain (Plan → Verify → Patch)
v2.0 → Agent-Y as standalone orchestrator, Agent-X as tool-calling worker

## Anti-Overengineering Gate (DATA FIRST)
Before v1.1 (local model): 20+ real pipeline runs with Reasoner active
Gate: autoresearch Check 4 passes — strategy → improved patch acceptance rate
Do NOT build v1.1 until data confirms v1 reasoning adds measurable value

## ENFORCEMENT RULE (inherited)
CLAUDE.md = suggestions (~80% compliance)
.claude/settings.json hooks = requirements (100% enforced)
.claude/rules/*.md = file-type standards (load on demand)
