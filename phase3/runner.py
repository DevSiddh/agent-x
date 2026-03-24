"""
phase3/runner.py — Poll loop for processing webhook events.

Continuously dequeues and processes events from webhook_queue via process_next().
Handles KeyboardInterrupt cleanly.

Run:
    python phase3/runner.py
"""

import os
import sys
import time
from pathlib import Path

import structlog
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from phase2.logging_config import configure_logging
from phase3.webhook_worker import process_next

configure_logging()
log = structlog.get_logger()


def _ping_healthcheck() -> None:
    """
    Ping HEALTHCHECK_URL if set — confirms runner is alive.
    Never raises.
    """
    url = os.environ.get("HEALTHCHECK_URL", "")
    if not url:
        return
    try:
        import requests
        requests.get(url, timeout=5)
    except Exception as exc:
        log.warning("runner.healthcheck_failed", error=str(exc))


def _alert_fatal(message: str) -> None:
    """
    POST an alert to ntfy.sh/{NTFY_TOPIC} on fatal errors.
    Never raises.
    """
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return
    try:
        import requests
        requests.post(f"https://ntfy.sh/{topic}", data=message.encode(), timeout=5)
    except Exception as exc:
        log.warning("runner.ntfy_failed", error=str(exc))


def poll_and_process(interval_seconds: int = 5) -> None:
    """
    Poll webhook_queue in a loop. For each event processed, log the result.
    Sleeps interval_seconds between polls. Exits cleanly on KeyboardInterrupt.

    Monitoring (0c):
    - Pings HEALTHCHECK_URL after every successful iteration (if env set)
    - Posts to ntfy.sh/{NTFY_TOPIC} on fatal errors (if env set)
    """
    log.info("runner.started", interval_seconds=interval_seconds)

    try:
        while True:
            try:
                entry = process_next()

                if entry is not None:
                    log.info(
                        "runner.processed",
                        repo=entry.repo,
                        run_id=entry.run_id,
                        category=entry.failure_category,
                        confidence=round(entry.confidence_score, 3),
                        decision=entry.decision,
                        mttr=entry.mttr_seconds,
                    )

                _ping_healthcheck()

            except Exception as exc:
                log.error("runner.fatal_error", error=str(exc))
                _alert_fatal(f"agent-x runner fatal error: {exc}")

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        log.info("runner.stopped", reason="KeyboardInterrupt")


if __name__ == "__main__":
    poll_and_process()
