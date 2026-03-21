# CLAUDE.md — v2.1 Real GitHub Webhook Integration
# Lives in phase3/ — same repo, same pipeline
# Last updated: 2026-03-20

## GIT RULES
- Contributor: CH Y SAI SIDDHARDHA only — Claude NEVER commits or pushes
- Branch: agent-x/fix-v21-<step> — never main
- No commit until ALL tests for that step pass
- Commit format: [v2.1-BN] description

## FIRST COMMAND EVERY SESSION
  python scripts/verify_env.py
  Fails → fix before touching anything

## SESSION START
1. Read @docs/progress.md → v2.1 section → find current PENDING step
2. Read @docs/session_prompts.md → step BN → execute fully
3. Update docs/progress.md after every completed file → STOP

## Hard Rules (no exceptions)
1. Accept ONLY: workflow_run + action=completed + conclusion=failure
2. Dedup check ALWAYS runs: (repo, run_id, run_attempt) before any processing
3. Log size ALWAYS capped at 200KB before parsing
4. GITHUB_TOKEN read lazily — inside function, never at module level
5. GitHub API 403 → exponential backoff (1s, 2s, 4s) → max 3 retries
6. confidence < 0.85 on real log → UNKNOWN → observer mode → STOP (no guess)
7. NEVER apply patch to main branch automatically
8. NEVER commit or push to target repo — human reviews first
9. run_attempt from webhook payload — always use latest, never default
10. Cleaner MUST strip ANSI codes + timestamps before classifier sees log

## Pipeline Entry Point (locked)
webhook event → Filter → Dedup → LogFetcher → log_cleaner_real → existing pipeline
Existing pipeline starts at: Classifier (phase2/classifier/regex_pass.py)
No changes to phase1/ or phase2/ internals

## v2.1 Done Condition
Real GitHub repo CI fails → webhook received → log fetched → MemoryEntry written
with real repo name + real run_id + real decision.

## Upgrade Queue (locked until v2.1 ships)
v2.2 → Auto-PR: create branch + PR with patch for human review
v2.3 → Multi-repo: one instance handles N repos
v3.0 → Production deployment (real server, not ngrok)

## Anti-Overengineering Gate (DATA FIRST)
Before v2.2 (auto-PR): 20+ real accepted fixes logged in memory.jsonl
Must confirm: patch quality on real repos before automating PR creation
