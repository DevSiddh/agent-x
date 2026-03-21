# v2.1 | Problems & Solutions
# Last updated: 2026-03-20

---

## P1 — Duplicate webhook events (idempotency)

- **Phase:** v2.1 / WebhookWorker
- **File:** phase3/webhook_worker.py
- **Problem:** GitHub resends webhook events on timeout or network issues.
  Same run_id processed twice → duplicate patches, duplicate memory entries.
- **Solution:** Dedup table in SQLite before any processing:
  ```python
  def already_processed(repo: str, run_id: int, run_attempt: int) -> bool:
      conn = sqlite3.connect(DB_PATH)
      row = conn.execute(
          "SELECT 1 FROM processed_runs WHERE repo=? AND run_id=? AND run_attempt=?",
          (repo, run_id, run_attempt)
      ).fetchone()
      conn.close()
      return row is not None

  def mark_processed(repo: str, run_id: int, run_attempt: int) -> None:
      conn = sqlite3.connect(DB_PATH)
      conn.execute(
          "INSERT OR IGNORE INTO processed_runs (repo, run_id, run_attempt) VALUES (?,?,?)",
          (repo, run_id, run_attempt)
      )
      conn.commit()
      conn.close()
  ```
- **Status:** PENDING — implement in webhook_worker.py

---

## P2 — Wrong event types triggering pipeline

- **Phase:** v2.1 / WebhookWorker
- **File:** phase3/webhook_worker.py
- **Problem:** GitHub sends many event types (push, PR, check_run, etc.).
  Processing non-failure events wastes API calls and pollutes memory.jsonl.
- **Solution:** Filter at queue dequeue time:
  ```python
  def should_process(event: dict) -> bool:
      return (
          event.get("action") == "completed"
          and event.get("conclusion") == "failure"
          and "run_id" in event
      )
  ```
  Log skipped events as `log.info("webhook.skipped", reason="not_failure")`.
- **Status:** PENDING — implement in webhook_worker.py

---

## P3 — Wrong run_attempt → stale logs fetched

- **Phase:** v2.1 / LogFetcher
- **File:** phase3/webhook_worker.py + phase1/log_fetcher/fetcher.py
- **Problem:** Re-runs create multiple attempts. Fetching without run_attempt
  returns logs from wrong attempt. Patch generated for already-fixed code.
- **Solution:** Pass run_attempt from webhook payload to fetcher:
  ```python
  run_attempt = event["workflow_run"]["run_attempt"]  # from webhook payload
  logs = fetch_logs(repo=repo, run_id=run_id, run_attempt=run_attempt, token=token)
  ```
  GitHub API endpoint: `GET /repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{attempt_number}/logs`
- **Status:** PENDING — add run_attempt param to fetcher.py

---

## P4 — Large logs blow memory / slow parsing

- **Phase:** v2.1 / Cleaner
- **File:** phase3/log_cleaner_real.py
- **Problem:** Large repos produce multi-MB log ZIPs. Loading full log into
  memory causes OOM or extreme slowness. Classifier gets irrelevant lines.
- **Solution:** Cap at 200KB before any parsing. Extract last failed step only:
  ```python
  MAX_LOG_BYTES = 200 * 1024  # 200KB

  def cap_log(raw: str) -> str:
      if len(raw.encode()) > MAX_LOG_BYTES:
          # Take last 200KB — failure is always near the end
          raw = raw.encode()[-MAX_LOG_BYTES:].decode(errors="ignore")
      return raw
  ```
- **Status:** PENDING — implement in log_cleaner_real.py

---

## P5 — GitHub API rate limit on log fetch

- **Phase:** v2.1 / LogFetcher
- **File:** phase1/log_fetcher/fetcher.py
- **Problem:** 403 or secondary rate limit hit when fetching logs for many repos.
  Unhandled → crash, lost run, no memory entry.
- **Solution:** Exponential backoff on 403:
  ```python
  import time

  def fetch_with_backoff(url: str, headers: dict, max_retries: int = 3) -> requests.Response:
      delays = [1, 2, 4]
      for attempt, delay in enumerate(delays[:max_retries]):
          resp = requests.get(url, headers=headers)
          if resp.status_code != 403:
              return resp
          log.warning("github.rate_limit", attempt=attempt, retry_in=delay)
          time.sleep(delay)
      raise RuntimeError("GitHub API rate limit exceeded after 3 retries")
  ```
- **Status:** PENDING — implement in fetcher.py

---

## P6 — Real logs have ANSI codes + timestamps (classifier confusion)

- **Phase:** v2.1 / Cleaner
- **File:** phase3/log_cleaner_real.py
- **Problem:** Real CI logs contain ANSI escape sequences (\x1b[31m), timestamps
  (2026-03-20T11:32:18Z), runner metadata ("##[group]", "##[endgroup]").
  Classifier regex patterns don't match noise-polluted lines.
- **Solution:** Strip before classifier sees the log:
  ```python
  import re

  ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
  TIMESTAMP   = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+")
  RUNNER_META = re.compile(r"^##\[(?:group|endgroup|warning|error|debug)\]")

  def clean_real_log(raw: str) -> list[str]:
      lines = []
      for line in raw.splitlines():
          line = ANSI_ESCAPE.sub("", line)
          line = TIMESTAMP.sub("", line)
          if RUNNER_META.match(line):
              continue
          if line.strip():
              lines.append(line.strip())
      return lines
  ```
- **Status:** PENDING — implement in log_cleaner_real.py

---

## P7 — Classifier confidence < 0.85 on noisy real logs

- **Phase:** v2.1 / Classifier + Pipeline
- **File:** phase2/classifier/regex_pass.py (no change), phase3/webhook_worker.py
- **Problem:** Real CI logs have mixed signals — classifier may return low confidence
  or wrong category. Guessing wrong category → wrong fix strategy → rejected patch.
- **Solution:** Treat low-confidence real logs as UNKNOWN, not as a guess:
  ```python
  if classifier_result.confidence < 0.85:
      log.info("classifier.unknown", confidence=classifier_result.confidence,
               repo=repo, run_id=run_id)
      # Observer mode — do not attempt repair
      return build_default_entry(run_id=run_id, repo=repo)
  ```
  UNKNOWN entries accumulate in memory.jsonl for later analysis and classifier tuning.
- **Status:** PENDING — enforce in webhook_worker.py (safety gate already handles this)
