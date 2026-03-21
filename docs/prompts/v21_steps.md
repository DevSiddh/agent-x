# Agent-X v2.1 | Steps B0–B3 (ACTIVE — IN PROGRESS)
# Current phase. Step B0 is READY.

---

## STEP B0 — v2.1 Spike (Validate Real GitHub Log Flow)
# First v2.1 step. DO NOT SKIP. Real log structure is unknown until this runs.

```
You are building Agent-X v2.1 — Real GitHub Webhook Integration.
Read phase3/CLAUDE.md, phase3/context.md, docs/v21_roadmap.md, docs/v21_problems.md before touching anything.

PREREQUISITE: webhook server must be running + ngrok tunnel active before this spike.

SPIKE GOAL: prove real GitHub CI logs flow through cleaner → classifier end-to-end.

BUILD spike/run_spike_real.py (~80 lines):
1. Read one real event from the SQLite queue (phase1/webhook/server.py writes to this)
   Queue DB: phase1/webhook/queue.db — table: webhook_events
   If queue empty: print "queue empty — push a commit to trigger a CI failure first" and exit
2. Extract: repo_full_name, run_id, run_attempt from event payload
3. Fetch log ZIP via GitHub API:
   GET https://api.github.com/repos/{repo}/actions/runs/{run_id}/attempts/{run_attempt}/logs
   Headers: Authorization: Bearer {GITHUB_TOKEN}, Accept: application/vnd.github+json
   GITHUB_TOKEN: read from os.environ inside function — never at module level
4. Extract text from ZIP (join all step log files, sorted order)
5. Apply cap_log() — take last 200KB
6. Apply clean_real_log() — strip ANSI, timestamps, runner metadata
7. Apply extract_failure_window() — last 20 lines around ERROR/Traceback/FAILED
8. Run classify() from phase2/classifier/regex_pass.py on cleaned lines
9. Print:
   - repo, run_id, run_attempt
   - category, confidence
   - cleaned error window (20 lines)
   - SPIKE PASS or SPIKE FAIL with reason

cap_log(), clean_real_log(), extract_failure_window() — implement inline in spike for now
(they move to phase3/log_cleaner_real.py in B1)

SPIKE PASS criteria:
- category is correct for the failure you triggered
- confidence >= 0.80
- extract_failure_window returns relevant error lines (not runner metadata)
- no crash on fetch or parse

SPIKE FAIL → stop. Report exact failure point. Do NOT proceed to B1 until spike passes.

DONE WHEN:
- python spike/run_spike_real.py → SPIKE PASS printed
- docs/progress.md updated: Step B0 DONE
```

---

## STEP B1 — v2.1: Real Log Cleaner
# Prerequisite: Step B0 spike PASSED

```
You are building Agent-X v2.1 — Real Log Cleaner module.
Read phase3/CLAUDE.md, docs/v21_problems.md (P4, P6) before touching anything.
Step B0 spike must be PASSED. Do not break existing tests (206+ passing).

BUILD THIS STEP:

1. phase3/__init__.py  (empty — package init)

2. phase3/log_cleaner_real.py
   - MAX_LOG_BYTES: int = 200 * 1024  (module-level constant)
   - ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
   - TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+")
   - RUNNER_META = re.compile(r"^##\[(?:group|endgroup|warning|error|debug)\]")

   Functions (all with type hints):
   - cap_log(raw: str) -> str
     If len(raw.encode()) > MAX_LOG_BYTES: take last 200KB. Return as string.
   - clean_real_log(raw: str) -> list[str]
     Strip ANSI codes, timestamps, runner metadata lines.
     Return non-empty stripped lines only.
   - extract_failure_window(lines: list[str], n: int = 20) -> list[str]
     Find last line matching: ERROR, Traceback, FAILED (case-sensitive).
     Return n//2 lines before + n//2 lines after that line.
     Falls back to last n lines if no error marker found.
   - structlog logging on every function entry
   - if __name__ == "__main__": smoke test with inline sample log string

3. tests/test_log_cleaner_real.py
   - Test cap_log: input > 200KB → output <= 200KB bytes
   - Test cap_log: input <= 200KB → unchanged
   - Test cap_log: takes last bytes (failure near end), not first bytes
   - Test clean_real_log: ANSI codes removed
   - Test clean_real_log: ISO timestamps removed
   - Test clean_real_log: runner metadata lines removed
   - Test clean_real_log: empty lines not in output
   - Test extract_failure_window: finds ERROR marker, returns N lines around it
   - Test extract_failure_window: falls back to last N lines when no error marker
   - Test extract_failure_window: correct line count returned

DONE WHEN:
- pytest tests/test_log_cleaner_real.py → all pass
- pytest tests/ → still 206+ pass (zero regressions)
- python phase3/log_cleaner_real.py → smoke test runs clean
- docs/progress.md updated: Step B1 DONE
```

---

## STEP B2 — v2.1: Webhook Worker
# Prerequisite: Step B1 DONE

```
You are building Agent-X v2.1 — WebhookWorker module.
Read phase3/CLAUDE.md, docs/v21_problems.md (P1 P2 P3 P5 P7) before touching anything.
Step B1 must be DONE. Do not break existing tests.

BUILD THIS STEP — phase3/webhook_worker.py:

DB_PATH for dedup: Path("phase3/processed_runs.db")  (separate from webhook queue.db)

Module-level: init_dedup_db() called once at import — creates processed_runs table if not exists
  Schema: CREATE TABLE IF NOT EXISTS processed_runs
            (repo TEXT, run_id INTEGER, run_attempt INTEGER,
             PRIMARY KEY (repo, run_id, run_attempt))

Functions (all with type hints, structlog on every decision):

- should_process(event: dict) -> bool  (P2)
  Returns True ONLY if: action=="completed" AND conclusion=="failure" AND "run_id" in event
  Log skipped events: log.info("webhook.skipped", reason="not_failure")

- already_processed(repo: str, run_id: int, run_attempt: int) -> bool  (P1)
  Check processed_runs table. Return True if row exists.

- mark_processed(repo: str, run_id: int, run_attempt: int) -> None  (P1)
  INSERT OR IGNORE into processed_runs.

- fetch_real_log(repo: str, run_id: int, run_attempt: int) -> str  (P3 P5)
  GITHUB_TOKEN read lazily: os.environ.get("GITHUB_TOKEN") — never at module level
  URL: https://api.github.com/repos/{repo}/actions/runs/{run_id}/attempts/{run_attempt}/logs
  Headers: Authorization: Bearer {token}, Accept: application/vnd.github+json
  Exponential backoff on 403: delays=[1,2,4], max 3 retries
  Log each retry: log.warning("github.rate_limit", attempt=N, retry_in=N)
  After 3 retries: raise RuntimeError("GitHub API rate limit exceeded after 3 retries")
  Extract ZIP in memory: join sorted step log files → return full raw string

- process_next() -> MemoryEntry | None
  1. Dequeue one event from phase1/webhook/queue.db (DELETE + return, atomic)
     SQL: SELECT id, payload FROM webhook_events ORDER BY id LIMIT 1
     Then: DELETE FROM webhook_events WHERE id=?
  2. Parse payload JSON → event dict
  3. should_process(event) → if False: log skip, return None
  4. Extract: repo = event["workflow_run"]["repository"]["full_name"]
              run_id = event["workflow_run"]["id"]
              run_attempt = event["workflow_run"]["run_attempt"]
  5. already_processed(repo, run_id, run_attempt) → if True: log dedup skip, return None
  6. fetch_real_log(repo, run_id, run_attempt) → raw log string
  7. cap_log(raw) → capped string
  8. clean_real_log(capped) → list[str]
  9. extract_failure_window(lines) → list[str] (error window)
  10. classify(error_window, repo=repo) from phase2/classifier/regex_pass.py
  11. If confidence < 0.85: log "classifier.unknown", return build_default_entry(run_id=str(run_id), repo=repo)
  12. Run existing pipeline from ContextBuilder onwards (import from phase2.pipeline internals)
  13. mark_processed(repo, run_id, run_attempt)
  14. Return MemoryEntry

- if __name__ == "__main__": smoke test with mock queue event (no real GitHub call)

tests/test_webhook_worker.py:
- Test should_process: True for action=completed + conclusion=failure
- Test should_process: False for success, cancelled, other actions
- Test should_process: False when run_id missing
- Test already_processed: False for new (repo, run_id, run_attempt)
- Test already_processed: True after mark_processed called
- Test dedup: same (repo, run_id, run_attempt) not processed twice
- Test fetch_real_log: exponential backoff on 403 (mock requests)
- Test fetch_real_log: raises RuntimeError after 3 failed retries
- Test process_next: returns None on empty queue
- Test process_next: returns None for non-failure event
- Test process_next: returns None for already-processed event
- Test process_next: confidence < 0.85 → returns default entry, no pipeline run

DONE WHEN:
- pytest tests/test_webhook_worker.py → all pass
- pytest tests/ → still 206+ pass (zero regressions)
- python phase3/webhook_worker.py → smoke test runs clean
- docs/progress.md updated: Step B2 DONE
```

---

## STEP B3 — v2.1: Integration + Runner + End-to-End
# Prerequisite: Step B2 DONE

```
You are completing Agent-X v2.1 — Real GitHub Webhook Integration.
Read phase3/CLAUDE.md, docs/v21_roadmap.md before touching anything.
Step B2 must be DONE. This is the finish line for v2.1.

BUILD THIS STEP:

1. phase3/runner.py
   - poll_and_process(interval_seconds: int = 5) -> None
     Loop: call process_next() → if MemoryEntry returned: log it → sleep interval_seconds
     Handles KeyboardInterrupt cleanly (log "runner.stopped" and exit)
     Structlog every event: repo, run_id, category, confidence, decision
   - if __name__ == "__main__": call poll_and_process()

2. tests/test_v21_integration.py
   Integration test — uses real SQLite but mocks GitHub API:
   - Test: push synthetic event into queue → process_next() → MemoryEntry written to memory.jsonl
     Event payload must have: action=completed, conclusion=failure, run_id, run_attempt,
     repository.full_name, workflow_run.id, workflow_run.run_attempt
   - Test: duplicate event → second call returns None (dedup working)
   - Test: non-failure event → returns None (filter working)
   - Test: runner.poll_and_process() processes queue then sleeps (mock process_next)

3. Update docs/progress.md — v2.1 section, all steps DONE

FINAL VERIFICATION (run these in order, no mocks):
1. pytest tests/ → all pass, zero regressions
2. Start webhook server: uvicorn phase1.webhook.server:app --port 8000
3. Start ngrok: ngrok http 8000
4. Set webhook URL in GitHub repo settings
5. Push commit to trigger CI failure
6. Run: python phase3/runner.py
7. Confirm: memory/memory.jsonl has new entry with real repo name + real run_id
8. Confirm: logs show repo + run_id + category + confidence + decision

DONE WHEN (v2.1 done condition):
- pytest tests/ → all pass (zero regressions on existing 206+ tests)
- memory/memory.jsonl has one entry with real repo + real run_id
- Logs show full pipeline for every real run
- docs/progress.md updated: v2.1 COMPLETE
```
