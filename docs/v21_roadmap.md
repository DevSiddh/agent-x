# v2.1 | Real GitHub Webhook Integration — Roadmap
# Last updated: 2026-03-20

---

## v2.1 Done Condition
Real GitHub repo CI fails → webhook fires → log fetched → pipeline runs →
MemoryEntry written with real repo + real run_id + real decision.

---

## Build Philosophy
- Spike first on a REAL failing repo before writing any module
- Cleaner must handle real logs before classifier is tested on them
- Never touch phase1/ or phase2/ internals — phase3/ is the entry layer only
- Data gate before v2.2: 20+ real accepted fixes before auto-PR

---

## STEP B0 — Spike (Validate Real Log Flow)
Priority: PROVE REAL LOGS WORK

| Task | File |
|------|------|
| Real log spike | spike/run_spike_real.py |

Spike spec:
- Create a test GitHub repo with a CI workflow that intentionally fails
  (e.g. import a missing module — same as syn_001)
- Start webhook server: uvicorn phase1.webhook.server:app --port 8000
- Start ngrok: ngrok http 8000
- Set webhook URL in GitHub repo settings (use ngrok URL)
- Push commit → GitHub sends webhook → server receives + queues
- Pull queued event → fetch log ZIP via GitHub API
- Run log_cleaner_real.clean_real_log() on raw log
- Run classify() on cleaned lines
- Print: category, confidence, cleaned error window

PASS: category correct, confidence ≥ 0.80, error window has relevant lines
FAIL: tells us exactly what cleaning or classifier fix is needed

DO NOT skip. Real log structure is unknown until this runs.

---

## STEP B1 — Real Log Cleaner
Priority: FOUNDATION FOR CLASSIFIER ACCURACY

| Task | File | Tests | Fixes |
|------|------|-------|-------|
| clean_real_log() | phase3/log_cleaner_real.py | tests/test_log_cleaner_real.py | P4 P6 |
| cap_log() | phase3/log_cleaner_real.py | tests/test_log_cleaner_real.py | P4 |

Module spec:
- clean_real_log(raw: str) -> list[str]
  Strip ANSI codes, timestamps (ISO + HH:MM:SS), runner metadata (##[group] etc.)
  Return clean lines only — no empty lines
- cap_log(raw: str) -> str
  Cap at 200KB (take last 200KB — failure is always near the end)
- extract_failure_window(lines: list[str], n: int = 20) -> list[str]
  Find last ERROR/Traceback/FAILED line, return N lines around it
  Falls back to last N lines if no error marker found
- structlog, type hints, pathlib, __main__ smoke test

---

## STEP B2 — Webhook Worker
Priority: MAIN ENTRY POINT

| Task | File | Tests | Fixes |
|------|------|-------|-------|
| WebhookWorker | phase3/webhook_worker.py | tests/test_webhook_worker.py | P1 P2 P3 P5 P7 |
| Dedup table init | phase3/webhook_worker.py | tests/test_webhook_worker.py | P1 |

Module spec:
- process_next() -> MemoryEntry | None
  Dequeues one event from SQLite queue (phase1/webhook/server.py writes this)
  Runs: filter → dedup → fetch → clean → classify → existing pipeline
  Returns MemoryEntry or None if skipped
- should_process(event: dict) -> bool  (P2)
  Returns True only for: action=completed + conclusion=failure
- already_processed(repo, run_id, run_attempt) -> bool  (P1)
  Checks processed_runs SQLite table
- mark_processed(repo, run_id, run_attempt) -> None  (P1)
- fetch_real_log(repo, run_id, run_attempt, token) -> str  (P3 P5)
  Uses run_attempt from webhook payload
  Exponential backoff on 403 (1s, 2s, 4s)
- GITHUB_TOKEN lazy inside function
- Log on every event: repo, run_id, run_attempt, action taken

---

## STEP B3 — Integration + End-to-End
Priority: WIRE AND VERIFY

| Task | File |
|------|------|
| phase3/__init__.py | empty package |
| Wire process_next() into a runner | phase3/runner.py |
| Integration test: real webhook → MemoryEntry | tests/test_v21_integration.py |
| Update docs/progress.md | — |

Runner spec (phase3/runner.py):
- poll_and_process(interval_seconds: int = 5) -> None
  Loop: dequeue → process_next() → sleep
  Runs until KeyboardInterrupt
  Structlog all events

DONE WHEN:
- pytest tests/ → all pass (zero regressions on existing 235 tests)
- Real GitHub repo CI fails → MemoryEntry written with real run_id
- Logs show repo + run_id + category + decision for every real run

---

## Status Tracker

| Step | Description | Status |
|------|-------------|--------|
| Step B0 | Spike — real CI log flow validated | PENDING |
| Step B1 | log_cleaner_real.py + tests | PENDING |
| Step B2 | webhook_worker.py + dedup + fetch | PENDING |
| Step B3 | Integration + runner + end-to-end | PENDING |

---

## Upgrade Queue (locked until v2.1 ships)
v2.2 → Auto-PR (create branch + PR) — needs 20+ real accepted fixes first
v2.3 → Multi-repo support
v3.0 → Orchestrator + shared state + Plan/Task loop (Y designs, X executes, feedback loop)
v3.1 → Project memory: goal + architecture + progress state
v4.0 → Fine-tune local model on prompt stack (after 50+ full loops, curated)
v4.1 → Idea in → working repo out (the north star)

Full vision → @docs/vision.md

---

## Key Decisions (locked)
1. phase3/ = entry layer only — never modify phase1/ or phase2/ internals
2. Dedup key = (repo, run_id, run_attempt) — stored in SQLite
3. Filter = workflow_run + conclusion=failure ONLY
4. Log cap = 200KB — take last 200KB (failure near end)
5. run_attempt from webhook payload — always latest
6. confidence < 0.85 on real log → UNKNOWN → observer mode (no guessing)
7. Auto-PR locked until 20+ real accepted fixes confirmed
