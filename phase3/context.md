# v2.1 | Real GitHub Webhook Integration — Context
# Max 80 lines — index only
# Last updated: 2026-03-20

---

## What Is v2.1
Connects Agent-XYZ to real GitHub repos. Replaces synthetic.jsonl with live
GitHub Actions failures delivered via webhook. Pipeline itself unchanged.

---

## New Flow (additions only)
GitHub webhook → Filter → Dedup → LogFetcher → Cleaner → existing pipeline

Existing pipeline (unchanged):
Classifier → SafetyGate → Thompson → ContextBuilder → Agent-Y → DeepSeek
→ Sanitiser → Executor → RegressionCheck → DecisionEngine → Memory

---

## New Components
phase3/webhook_worker.py   — dequeue SQLite → filter → dedup → fetch → clean
phase3/log_cleaner_real.py — ANSI strip, timestamp removal, last-failed-step extract

---

## Event Filter Rules (hard)
Accept only: workflow_run event + action=completed + conclusion=failure
Reject all:  push, pull_request, success, cancelled, skipped

---

## Idempotency Key
(repo_full_name, run_id, run_attempt) — stored in SQLite processed_runs table
Skip if already in table. Log as "dedup.skipped".

---

## Log Fetch Rules
- Use run_attempt from webhook payload (latest attempt, not default)
- Cap raw log at 200KB before parsing
- Extract last failed step only if multi-step log
- GITHUB_TOKEN scope required: repo + actions:read

---

## GitHub API Rate Limit Guard
403 or secondary rate limit → exponential backoff: 1s, 2s, 4s → max 3 retries
Log each retry. After 3 → log "github.rate_limit_exceeded" → skip run.

---

## Classifier Fallback (real logs)
confidence < 0.85 on real log → category=UNKNOWN → observer mode → pipeline stops
Log as "classifier.unknown" with raw error lines for later analysis.
Do NOT guess category on real repos — unknown is safer than wrong.

---

## Cleaner Spec (real logs differ from synthetic)
Must strip: ANSI escape codes (\x1b[...m), timestamps (HH:MM:SS), runner metadata
Must keep:  error message lines, stack trace, file references
Must do:    extract last N=20 lines of the failed step (not whole log)

---

## Observability (log these on every run)
repo, run_id, run_attempt, category, confidence, pipeline_decision, mttr_seconds

---

## Spike Acceptance Criteria
PASS: classifier correct category ≥ 80% on 5–10 real CI failures
PASS: extract_error_window returns relevant lines (not metadata)
PASS: no crash on large logs (>200KB)
FAIL: any of above fails → fix cleaner/classifier before Step B1

---

## v2.1 Done Condition
Real GitHub repo CI fails → webhook received → log fetched → pipeline runs
→ MemoryEntry written with real repo + real run_id.

---

## Key Files
→ @phase3/webhook_worker.py       — main entry point
→ @phase3/log_cleaner_real.py     — real log cleaning
→ @docs/v21_problems.md           — P1..P7 risks
→ @docs/v21_roadmap.md            — build steps B0..B3
→ @docs/progress.md               — v2.1 status section
→ @docs/session_prompts.md        — steps B0..B3
