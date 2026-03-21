"""
Step B0 — Spike: Validate Real GitHub Log Flow
Reads one event from webhook_queue → fetches real CI log → cleans → classifies.
Run: python spike/run_spike_real.py
"""

import io
import os
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase2.classifier.regex_pass import classify

# ── DB ─────────────────────────────────────────────────────────────────────────
DB_PATH = Path(__file__).resolve().parents[1] / "phase1" / "webhook" / "queue.db"

# ── Inline cleaner functions (move to phase3/log_cleaner_real.py in B1) ───────
MAX_LOG_BYTES: int = 200 * 1024
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+")
RUNNER_META = re.compile(r"^##\[(?:group|endgroup|warning|error|debug)\]")


def cap_log(raw: str) -> str:
    encoded = raw.encode("utf-8", errors="ignore")
    if len(encoded) > MAX_LOG_BYTES:
        encoded = encoded[-MAX_LOG_BYTES:]
    return encoded.decode("utf-8", errors="ignore")


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


def extract_failure_window(lines: list[str], n: int = 20) -> list[str]:
    markers = {"ERROR", "Traceback", "FAILED", "Error:", "error:"}
    last_idx = -1
    for i, line in enumerate(lines):
        if any(m in line for m in markers):
            last_idx = i
    if last_idx == -1:
        return lines[-n:]
    half = n // 2
    start = max(0, last_idx - half)
    end = min(len(lines), last_idx + half)
    return lines[start:end]


# ── Log fetcher (lazy token) ───────────────────────────────────────────────────
def _get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError("GITHUB_TOKEN not set")
    return token


def fetch_log_zip(repo: str, run_id: int, run_attempt: int) -> str:
    token = _get_token()
    url = (
        f"https://api.github.com/repos/{repo}/actions/runs/"
        f"{run_id}/attempts/{run_attempt}/logs"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    if resp.status_code == 404:
        raise RuntimeError(f"Logs not found (404) — run_id={run_id} attempt={run_attempt}")
    if resp.status_code != 200:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text[:200]}")

    parts: list[str] = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith(".txt"):
                parts.append(zf.read(name).decode("utf-8", errors="ignore"))
    return "\n".join(parts)


# ── Main spike ────────────────────────────────────────────────────────────────
def main() -> None:
    # 1. Load .env if dotenv available
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass

    # 2. Read one event from queue
    if not DB_PATH.exists():
        print(f"SPIKE FAIL — queue.db not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, repo_name, run_id FROM webhook_queue "
        "WHERE status='pending' ORDER BY id LIMIT 1"
    ).fetchone()
    conn.close()

    if row is None:
        print("queue empty — push a commit to trigger a CI failure first")
        sys.exit(0)

    row_id, repo, run_id = row
    run_attempt = 1  # NOTE: server.py doesn't store run_attempt — defaulting to 1
    print(f"\nrepo        : {repo}")
    print(f"run_id      : {run_id}")
    print(f"run_attempt : {run_attempt}  (default — not stored in queue schema)")

    # 3. Fetch log ZIP
    print("\nFetching logs from GitHub API...")
    try:
        raw = fetch_log_zip(repo, run_id, run_attempt)
    except RuntimeError as exc:
        print(f"SPIKE FAIL — fetch error: {exc}")
        sys.exit(1)

    print(f"raw log size: {len(raw.encode())} bytes")

    # 4. Cap
    capped = cap_log(raw)
    print(f"after cap   : {len(capped.encode())} bytes")

    # 5. Clean
    cleaned = clean_real_log(capped)
    print(f"cleaned lines: {len(cleaned)}")

    # 6. Extract failure window
    window = extract_failure_window(cleaned, n=20)
    print(f"\n--- error window ({len(window)} lines) ---")
    for line in window:
        print(f"  {line}")
    print("---")

    # 7. Classify
    result = classify(window, repo=repo)
    print(f"\ncategory    : {result.category}")
    print(f"confidence  : {result.confidence:.3f}")
    print(f"keyword     : {result.keyword}")
    print(f"affected    : {result.affected_file}")

    # 8. Pass/Fail verdict
    print()
    if result.confidence >= 0.80 and result.category != "UNKNOWN":
        print("SPIKE PASS — category classified, confidence >= 0.80, window looks relevant")
        sys.exit(0)
    else:
        reason = (
            f"confidence {result.confidence:.3f} < 0.80"
            if result.confidence < 0.80
            else f"category UNKNOWN"
        )
        print(f"SPIKE FAIL — {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
