"""
calibrate_threshold.py — Confidence Threshold Calibration
Reads memory/memory.jsonl and sweeps thresholds 0.50–0.99 in steps of 0.05.
Prints precision, recall, F1 at each threshold and recommends the best one.

Usage:
    python scripts/calibrate_threshold.py
"""

import json
from pathlib import Path


REPO_ROOT: Path = Path(__file__).resolve().parents[1]
MEMORY_PATH: Path = REPO_ROOT / "memory" / "memory.jsonl"
CURRENT_THRESHOLD: float = 0.85


def load_entries(memory_path: Path) -> list[dict]:
    """Load all entries from memory.jsonl. Returns empty list if file missing."""
    if not memory_path.exists():
        return []
    entries: list[dict] = []
    with open(memory_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def compute_stats(
    entries: list[dict],
    threshold: float,
) -> tuple[int, int, float, float, float]:
    """
    For a given threshold, compute counts and metrics.

    Returns:
        (processed, accepted_above, precision, recall, f1)
        - processed       = entries with confidence_score >= threshold
        - accepted_above  = entries where decision==accepted AND confidence >= threshold
        - precision       = accepted_above / processed  (0 if processed == 0)
        - recall          = accepted_above / total_accepted  (0 if total_accepted == 0)
        - f1              = harmonic mean of precision and recall  (0 if both zero)
    """
    total_accepted: int = sum(
        1 for e in entries if e.get("decision") == "accepted"
    )

    processed: int = 0
    accepted_above: int = 0

    for entry in entries:
        confidence: float = float(entry.get("confidence_score") or 0.0)
        decision: str = entry.get("decision", "")
        if confidence >= threshold:
            processed += 1
            if decision == "accepted":
                accepted_above += 1

    precision: float = (accepted_above / processed) if processed > 0 else 0.0
    recall: float = (accepted_above / total_accepted) if total_accepted > 0 else 0.0

    if precision + recall > 0:
        f1: float = 2.0 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    return processed, accepted_above, precision, recall, f1


def build_threshold_table(
    entries: list[dict],
) -> list[tuple[float, int, int, float, float, float]]:
    """
    Sweep thresholds from 0.50 to 0.99 inclusive in 0.05 steps.

    Returns list of (threshold, processed, accepted, precision, recall, f1).
    """
    rows: list[tuple[float, int, int, float, float, float]] = []
    threshold: float = 0.50
    while threshold <= 0.99 + 1e-9:
        t = round(threshold, 2)
        processed, accepted, precision, recall, f1 = compute_stats(entries, t)
        rows.append((t, processed, accepted, precision, recall, f1))
        threshold += 0.05
    return rows


def find_best_threshold(
    rows: list[tuple[float, int, int, float, float, float]],
) -> tuple[float, float]:
    """Return (best_threshold, best_f1) — highest F1, ties broken by lowest threshold."""
    best_t: float = rows[0][0]
    best_f1: float = rows[0][5]
    for t, _, _, _, _, f1 in rows:
        if f1 > best_f1:
            best_f1 = f1
            best_t = t
    return best_t, best_f1


def get_current_stats(
    rows: list[tuple[float, int, int, float, float, float]],
    current: float,
) -> tuple[float, float, float] | None:
    """Return (precision, recall, f1) for the current threshold, or None if not found."""
    for t, _, _, precision, recall, f1 in rows:
        if abs(t - current) < 1e-9:
            return precision, recall, f1
    return None


def print_table(
    entries: list[dict],
    rows: list[tuple[float, int, int, float, float, float]],
    current_threshold: float,
) -> None:
    """Print the full calibration table and summary."""
    total_entries: int = len(entries)
    total_accepted: int = sum(1 for e in entries if e.get("decision") == "accepted")

    print("=== Confidence Threshold Calibration ===")
    print(f"Total entries in memory: {total_entries}")
    print(f"Total accepted:          {total_accepted}")
    print()
    print(f"{'threshold':>9} | {'processed':>9} | {'accepted':>8} | {'precision':>9} | {'recall':>6} | {'F1':>7}")
    print("-" * 65)

    for t, processed, accepted, precision, recall, f1 in rows:
        marker: str = "  << current" if abs(t - current_threshold) < 1e-9 else ""
        print(
            f"   {t:.2f}   |"
            f"    {processed:>5}    |"
            f"   {accepted:>5}    |"
            f"   {precision:.3f}   |"
            f" {recall:.3f}  |"
            f" {f1:.3f}"
            f"{marker}"
        )

    print("-" * 65)

    best_t, best_f1 = find_best_threshold(rows)
    current_stats = get_current_stats(rows, current_threshold)
    current_f1: float = current_stats[2] if current_stats is not None else 0.0

    print(f"\nRecommended threshold: {best_t:.2f}  (F1={best_f1:.3f})")
    print(f"Current threshold:     {current_threshold:.2f}  (F1={current_f1:.3f})")


def main() -> None:
    entries: list[dict] = load_entries(MEMORY_PATH)

    if not entries:
        print(f"No entries found at {MEMORY_PATH}")
        return

    rows = build_threshold_table(entries)
    print_table(entries, rows, CURRENT_THRESHOLD)


if __name__ == "__main__":
    main()
