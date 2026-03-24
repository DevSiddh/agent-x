"""
dashboard/data.py
Pure-Python data loading layer for the Streamlit dashboard.
Reads memory.jsonl and thompson_state.json — no Streamlit imports.
Fully testable with pytest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path helpers (lazy — never module-level)
# ---------------------------------------------------------------------------


def _memory_path() -> Path:
    return Path(__file__).resolve().parents[1] / "memory" / "memory.jsonl"


def _thompson_path() -> Path:
    return Path(__file__).resolve().parents[1] / "memory" / "thompson_state.json"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_entries() -> list[dict[str, Any]]:
    """
    Load all entries from memory.jsonl.
    Returns empty list if file missing or unreadable.
    """
    path = _memory_path()
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:  # noqa: BLE001
        return []
    return entries


def load_thompson_state() -> dict[str, dict[str, int]]:
    """
    Load thompson_state.json.
    Returns empty dict if missing or unreadable.
    """
    path = _thompson_path()
    if not path.exists():
        return {}
    try:
        raw: dict[str, dict[str, int]] = json.loads(path.read_text(encoding="utf-8"))
        return raw
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------


def run_summary(entries: list[dict[str, Any]]) -> dict[str, int]:
    """
    Count decisions: accepted / rejected / abstained / structural / observer.
    """
    counts: dict[str, int] = {
        "accepted": 0,
        "rejected": 0,
        "abstained": 0,
        "structural": 0,
        "total": 0,
    }
    for e in entries:
        counts["total"] += 1
        d = e.get("decision", "")
        if d in counts:
            counts[d] += 1
    return counts


def category_breakdown(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Count runs per failure_category."""
    counts: dict[str, int] = {}
    for e in entries:
        cat = e.get("failure_category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def cost_saved_summary(entries: list[dict[str, Any]]) -> dict[str, int | float]:
    """
    Calculate LLM cost savings from memory reuse and gateway bypasses.

    DeepSeek-chat pricing: ~$0.28 / 1M tokens input.
    Estimated tokens per run: 1000 (prompt + context).
    Cost per LLM call ≈ $0.00028.
    """
    deepseek_calls = sum(1 for e in entries if e.get("model_used") == "deepseek-chat")
    memory_reuse = sum(1 for e in entries if e.get("model_used") == "memory_reuse")
    gateway_hits = sum(1 for e in entries if e.get("model_used") == "gateway")
    bypassed = memory_reuse + gateway_hits

    cost_per_call = 0.00028  # $0.28 / 1M tokens × ~1000 tokens/call
    cost_saved = round(bypassed * cost_per_call, 4)

    return {
        "deepseek_calls": deepseek_calls,
        "memory_reuse": memory_reuse,
        "gateway_hits": gateway_hits,
        "bypassed_total": bypassed,
        "cost_saved_usd": cost_saved,
    }


def thompson_table(state: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    """
    Convert thompson_state dict to a list of dicts for display.
    Adds win_rate and total_trials columns.
    Sorted by win_rate descending.
    """
    rows: list[dict[str, Any]] = []
    for arm, vals in state.items():
        alpha = vals.get("alpha", 1)
        beta = vals.get("beta", 1)
        total = alpha + beta - 2  # subtract initial Beta(1,1) baseline
        win_rate = round((alpha - 1) / max(total, 1), 4) if total > 0 else 0.0
        rows.append(
            {
                "arm": arm,
                "alpha": alpha,
                "beta": beta,
                "trials": total,
                "win_rate": win_rate,
            }
        )
    return sorted(rows, key=lambda r: r["win_rate"], reverse=True)


def rejection_breakdown(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Count rejection_reason values across all rejected/abstained entries."""
    counts: dict[str, int] = {}
    for e in entries:
        if e.get("decision") not in ("rejected", "abstained", "structural"):
            continue
        reason = e.get("rejection_reason", "") or "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def acceptance_rate(summary: dict[str, int]) -> float:
    """Accepted / total (excluding observer-mode abstains if desired)."""
    total = summary.get("total", 0)
    if total == 0:
        return 0.0
    return round(summary["accepted"] / total * 100, 1)


if __name__ == "__main__":
    entries = load_entries()
    state = load_thompson_state()

    summary = run_summary(entries)
    cost = cost_saved_summary(entries)
    table = thompson_table(state)
    cats = category_breakdown(entries)
    rejections = rejection_breakdown(entries)

    print(f"Total runs  : {summary['total']}")
    print(f"Accepted    : {summary['accepted']}  ({acceptance_rate(summary)}%)")
    print(f"Rejected    : {summary['rejected']}")
    print(f"Abstained   : {summary['abstained']}")
    print(f"Structural  : {summary['structural']}")
    print()
    print(f"LLM bypassed: {cost['bypassed_total']}  (memory={cost['memory_reuse']} gateway={cost['gateway_hits']})")
    print(f"Cost saved  : ${cost['cost_saved_usd']}")
    print()
    print("Thompson arms:")
    for row in table:
        print(f"  {row['arm']:30s}  win={row['win_rate']:.2%}  α={row['alpha']} β={row['beta']}  n={row['trials']}")
    print()
    print("Categories:", cats)
    print("Rejection reasons:", rejections)
