"""
harness.py
Local test harness for Agent-X — no GitHub webhook required.

Discovers test_repo_cases/cases/*/, runs each broken main.py locally,
feeds the error output to the classifier + full pipeline, verifies the fix.

Skips automatically:
  - bld_*  : require Docker (wrong error type captured locally)
  - Any case whose main.py exits 0 (packages installed, no error to classify)

Usage:
    python harness.py                  # run all runnable cases
    python harness.py run_l1 cfg_l2   # specific cases
    python harness.py --no-llm        # classify only, skip DeepSeek (no API cost)
    python harness.py --no-llm run_l1 # combine
"""

import argparse
import subprocess
import sys
import uuid
from pathlib import Path

import structlog
import structlog.dev
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

load_dotenv(_REPO_ROOT / ".env")

# Route structlog to stderr so table output stays clean on stdout
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

from phase2.classifier.regex_pass import classify
from phase2.classifier.safety_gate import check as gate_check
from phase2.context_builder import build_context
from phase2.executor.runner import apply_patch, rollback
from phase2.memory.store import append, build_default_entry
from phase2.patch_gen.worker import generate_patch

log = structlog.get_logger()

CASES_ROOT = _REPO_ROOT / "test_repo_cases" / "cases"

# Skip prefixes — wrong error type captured locally
_SKIP_PREFIXES: tuple[str, ...] = ("bld_",)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_main(case_path: Path) -> tuple[list[str], int]:
    """
    Run main.py in the case directory.
    Returns (error_lines, exit_code).
    """
    result = subprocess.run(
        [sys.executable, str(case_path / "main.py")],
        capture_output=True,
        text=True,
        cwd=case_path,
        timeout=30,
    )
    output = result.stdout + result.stderr
    lines = [line for line in output.splitlines() if line.strip()]
    return lines, result.returncode


def _ensure_git_repo(case_path: Path) -> None:
    """Initialise case dir as git repo if not already done."""
    if (case_path / ".git").exists():
        return
    git = ["git", "-C", str(case_path)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "test@test.com"], check=True)
    subprocess.run([*git, "config", "user.name", "Test"], check=True)
    subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
    subprocess.run([*git, "config", "core.eol", "lf"], check=True)
    (case_path / ".gitattributes").write_text("* text eol=lf\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "broken baseline"], check=True)
    log.info("harness.git_init", case=case_path.name)


# ---------------------------------------------------------------------------
# Single case runner
# ---------------------------------------------------------------------------

def run_case(case_id: str, no_llm: bool = False) -> dict:
    """
    Run one harness case end-to-end.

    Returns a result dict with keys:
        case_id, run_id, category, confidence, decision, verify_pass, error
    """
    case_path = CASES_ROOT / case_id
    run_id = str(uuid.uuid4())[:8]
    repo = f"test_repo_cases/{case_id}"

    result: dict = {
        "case_id":    case_id,
        "run_id":     run_id,
        "category":   None,
        "confidence": 0.0,
        "decision":   "skipped",
        "verify_pass": None,
        "error":      "",
    }

    # Step 1 — run broken code, capture error log
    error_lines, exit_code = _run_main(case_path)

    if exit_code == 0:
        result["error"] = "passes locally (packages installed) — no error to classify"
        log.info("harness.case_skip", case=case_id, reason="exit_0")
        return result

    # Step 2 — classify
    clf = classify(error_lines, repo=repo)
    result["category"]   = clf.category
    result["confidence"] = clf.confidence
    log.info("harness.classified", case=case_id, category=clf.category, confidence=clf.confidence)

    # Step 3 — safety gate
    gate = gate_check(clf)
    if not gate.passed:
        result["decision"] = "observer"
        result["error"] = f"confidence {clf.confidence:.2f} < 0.85"
        log.info("harness.observer", case=case_id, confidence=clf.confidence)
        return result

    # Step 4 — classify-only mode (no API cost)
    if no_llm:
        result["decision"] = "classify_only"
        return result

    # Step 5 — full pipeline: context → patch → apply → verify
    _ensure_git_repo(case_path)
    rollback(case_path)

    outcome = build_default_entry(run_id=run_id, repo=repo)

    try:
        # Context
        context = build_context(clf, case_path, error_lines=error_lines)

        # Patch generation
        worker = generate_patch(
            error_lines=error_lines,
            classifier_result=clf,
            context=context,
        )

        # Apply
        apply_result = apply_patch(worker.diff, case_path)
        result["patch_applied"] = apply_result.success

        if apply_result.success:
            # Verify fix
            _, verify_exit = _run_main(case_path)
            result["verify_pass"] = verify_exit == 0
            result["decision"] = "accepted" if verify_exit == 0 else "rejected"
            log.info(
                "harness.verify",
                case=case_id,
                passed=result["verify_pass"],
                decision=result["decision"],
            )
        else:
            result["decision"] = "rejected"
            result["error"] = apply_result.error
            log.warning("harness.apply_failed", case=case_id, error=apply_result.error)

        outcome = outcome.model_copy(update={
            "failure_category": clf.category,
            "bug_signature":    clf.bug_signature,
            "confidence_score": clf.confidence,
            "patch_applied":    worker.diff,
            "model_used":       worker.model_used,
            "retries_used":     worker.attempt - 1,
            "decision":         result["decision"],
            "source":           "harness",
        })

    except Exception as exc:
        result["decision"] = "error"
        result["error"]    = str(exc)
        outcome = outcome.model_copy(update={
            "failure_category": clf.category,
            "bug_signature":    clf.bug_signature,
            "confidence_score": clf.confidence,
            "decision":         "abstained",
            "error":            str(exc),
            "source":           "harness",
        })
        log.error("harness.exception", case=case_id, error=str(exc))

    finally:
        rollback(case_path)
        append(outcome)

    return result


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Agent-X local test harness")
    parser.add_argument("cases", nargs="*", help="specific case IDs (default: all)")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="classify only — skip DeepSeek, no API cost",
    )
    args = parser.parse_args()

    # Discover cases
    if args.cases:
        case_ids = list(args.cases)
    else:
        case_ids = sorted(p.name for p in CASES_ROOT.iterdir() if p.is_dir())

    # Partition: prefixed skip vs runnable
    skipped_docker = [c for c in case_ids if any(c.startswith(p) for p in _SKIP_PREFIXES)]
    runnable       = [c for c in case_ids if c not in skipped_docker]

    mode_label = " [classify only]" if args.no_llm else ""
    print(f"\n{'='*68}")
    print(f"Agent-X Harness — {len(runnable)} cases{mode_label}")
    if skipped_docker:
        print(f"Skipped (Docker): {', '.join(skipped_docker)}")
    print(f"{'='*68}")
    print(f"{'':4}{'Case':<12} {'Category':<18} {'Conf':>5}  {'Decision':<14} {'Verify'}")
    print(f"{'-'*68}")

    results = []
    for case_id in runnable:
        r = run_case(case_id, no_llm=args.no_llm)
        results.append(r)

        verify_str = ""
        if r["verify_pass"] is True:
            verify_str = "PASS"
        elif r["verify_pass"] is False:
            verify_str = "FAIL"

        skip_decisions = ("skipped", "classify_only", "observer")
        if r["decision"] == "accepted":
            icon = "PASS"
        elif r["decision"] in skip_decisions:
            icon = "SKIP"
        else:
            icon = "FAIL"

        print(
            f"{icon}  {case_id:<10} "
            f"{(r['category'] or '-'):<18} "
            f"{r['confidence']:>4.2f}  "
            f"{r['decision']:<14} "
            f"{verify_str}"
        )
        if r["error"] and r["decision"] not in skip_decisions:
            print(f"      └─ {r['error'][:70]}")

    # Summary
    accepted      = sum(1 for r in results if r["decision"] == "accepted")
    skipped_local = sum(1 for r in results if r["decision"] == "skipped")
    observer      = sum(1 for r in results if r["decision"] == "observer")
    eligible      = len(runnable) - skipped_local - observer

    print(f"{'='*68}")
    print(
        f"Result: {accepted}/{eligible} accepted  |  "
        f"{skipped_local} pass locally  |  "
        f"{observer} observer mode"
    )
    print(f"{'='*68}\n")


if __name__ == "__main__":
    main()
