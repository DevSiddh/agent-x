"""
phase2/memory/store.py
Append-only JSONL memory store. Tracks every pipeline run (P8).
Deduplication on (repo + bug_signature) before write (P6).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, Field

log = structlog.get_logger()

# Lazy path — never evaluated at module level
def _memory_path() -> Path:
    return Path(__file__).resolve().parents[2] / "memory" / "memory.jsonl"


# ---------------------------------------------------------------------------
# Schema — matches context.md exactly
# ---------------------------------------------------------------------------

class MemoryEntry(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    run_id: str
    timestamp: str
    source: str
    repo: str
    failure_category: str
    bug_signature: str                    # repo:ErrorType:keyword:file (P12)
    confidence_score: float = Field(ge=0.0, le=1.0)
    mode: str                             # "repair" | "observer"
    patch_applied: str
    lines_changed: int = 0
    model_used: str
    sandbox_result: str                   # "pass" | "fail" | "skipped"
    regression_introduced: bool = False
    retries_used: int = 0
    mttr_seconds: float = 0.0
    decision: str                         # "accepted"|"rejected"|"escalated"|"abstained"
    success_count: int = 0
    fail_count: int = 0
    error: str = ""
    test_summary: str = ""     # e.g. "12 passed, 0 failed" — for weak-success filtering (C0)
    rejection_reason: str = "" # E1 — why rejected: prompt_issue|context_issue|logic_issue|size_issue|security_issue|unknown
    diagnosis: str = ""        # D1 — Agent-Y one-sentence diagnosis: what is broken and why
    pr_url: str = ""           # D1 — GitHub PR URL (set after create_pr succeeds)
    issue_url: str = ""        # D1 — GitHub Issue URL (set after open_structural_issue succeeds)


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def append(entry: MemoryEntry) -> None:
    """
    Append a MemoryEntry to memory.jsonl.
    Never raises — all errors are logged and swallowed. (P8)
    """
    try:
        path = _memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        log.info("memory.appended", run_id=entry.run_id, decision=entry.decision)
    except Exception as e:
        log.error("memory.append_failed", error=str(e))


def already_fixed(bug_signature: str, repo: str) -> bool:
    """
    Check if an accepted fix for this (repo + bug_signature) already exists. (P6)

    Returns:
        True if a matching accepted entry exists, False otherwise.
    """
    path = _memory_path()
    if not path.exists():
        return False

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if (
                        entry.get("bug_signature") == bug_signature
                        and entry.get("repo") == repo
                        and entry.get("decision") == "accepted"
                    ):
                        log.info(
                            "memory.already_fixed",
                            bug_signature=bug_signature,
                            repo=repo,
                        )
                        return True
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        log.error("memory.already_fixed_error", error=str(e))

    return False


def get_similar(bug_signature: str, limit: int = 3) -> list[MemoryEntry]:
    """
    Return last N entries with the same failure_category as this bug_signature.
    Used by ContextBuilder to provide past fix context.

    Args:
        bug_signature: Format repo:ErrorType:keyword:file — ErrorType is parts[1]
        limit:         Max entries to return (most recent first)
    """
    path = _memory_path()
    if not path.exists():
        return []

    # Extract category from signature — format: repo:Category:keyword:file
    parts = bug_signature.split(":")
    target_category = parts[1] if len(parts) >= 2 else ""

    matches: list[MemoryEntry] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("failure_category") == target_category:
                        matches.append(MemoryEntry(**data))
                except (json.JSONDecodeError, Exception):
                    continue
    except Exception as e:
        log.error("memory.get_similar_error", error=str(e))
        return []

    # Return last N (most recent)
    return matches[-limit:]


def build_default_entry(run_id: str, repo: str) -> MemoryEntry:
    """
    Build a MemoryEntry with safe defaults for use in pipeline finally blocks. (P8)
    Ensures memory is always written even on unhandled exceptions.
    """
    return MemoryEntry(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        source="pipeline",
        repo=repo,
        failure_category="unknown",
        bug_signature=f"{repo}:unknown:unknown:unknown",
        confidence_score=0.0,
        mode="observer",
        patch_applied="",
        lines_changed=0,
        model_used="deepseek-chat",
        sandbox_result="skipped",
        regression_introduced=False,
        retries_used=0,
        mttr_seconds=0.0,
        decision="abstained",
        success_count=0,
        fail_count=0,
        error="",
    )


if __name__ == "__main__":
    import os
    import tempfile

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    # Use temp file so smoke test doesn't pollute real memory.jsonl
    tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tmp.close()

    # Monkey-patch _memory_path for smoke test
    import phase2.memory.store as _store
    _real_path = _store._memory_path
    _store._memory_path = lambda: Path(tmp.name)

    try:
        # 1 — Write 3 entries
        e1 = build_default_entry("run-001", "smoke/repo")
        e1 = e1.model_copy(update={
            "failure_category": "DependencyError",
            "bug_signature": "smoke/repo:DependencyError:pkg_resources:requirements.txt",
            "decision": "accepted",
        })
        e2 = build_default_entry("run-002", "smoke/repo")
        e2 = e2.model_copy(update={
            "failure_category": "DependencyError",
            "bug_signature": "smoke/repo:DependencyError:pkg_resources:requirements.txt",
            "decision": "rejected",
        })
        e3 = build_default_entry("run-003", "other/repo")
        e3 = e3.model_copy(update={
            "failure_category": "ConfigError",
            "bug_signature": "other/repo:ConfigError:no_such_table:app/database.py",
            "decision": "accepted",
        })

        append(e1)
        append(e2)
        append(e3)
        print("PASS  append: 3 entries written")

        # 2 — Dedup check
        assert already_fixed("smoke/repo:DependencyError:pkg_resources:requirements.txt", "smoke/repo") is True
        assert already_fixed("smoke/repo:DependencyError:pkg_resources:requirements.txt", "other/repo") is False
        assert already_fixed("new:sig", "smoke/repo") is False
        print("PASS  already_fixed: dedup works correctly")

        # 3 — Get similar
        similar = get_similar("smoke/repo:DependencyError:pkg_resources:requirements.txt", limit=3)
        assert len(similar) == 2
        assert all(s.failure_category == "DependencyError" for s in similar)
        print(f"PASS  get_similar: returned {len(similar)} entries")

        # 4 — append never raises on bad path
        _store._memory_path = lambda: Path("/invalid/path/that/does/not/exist/memory.jsonl")
        append(e1)  # should not raise
        print("PASS  append: never raises on bad path")

    finally:
        _store._memory_path = _real_path
        os.unlink(tmp.name)

    print("store.py smoke test PASSED")
