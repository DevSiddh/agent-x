"""
phase2/pipeline.py
Agent-X v1.3 — full autonomous repair pipeline + Thompson Sampling.
Orchestrates all stages in strict order. try/finally guarantees memory write (P8).

Usage:
    python phase2/pipeline.py          → runs all 5 synthetic cases
    python phase2/pipeline.py syn_001  → runs single case
"""

import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog
from dotenv import load_dotenv

# Path setup — allows running directly or as package
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load .env so DEEPSEEK_API_KEY is available when running directly
load_dotenv(_REPO_ROOT / ".env")

from phase2.context_builder import build_context
from phase2.logging_config import configure_logging
configure_logging()

from agent_y.reasoner import ReasonerError, reason
from phase1.log_fetcher.cleaner import clean_and_extract
from phase2.classifier.regex_pass import ClassifierResult, classify, classify_with_fallback
from phase2.classifier.safety_gate import check as gate_check
from phase2.executor.regression import TestReport, check_regression, run_tests, run_tests_stable
from phase2.executor.runner import apply_patch, check_syntax, rollback
from phase2.memory.store import MemoryEntry, append, build_default_entry
from phase2.patch_gen.sanitiser import validate_patch
from phase2.patch_gen.worker import generate_patch

log = structlog.get_logger()

JSONL_PATH = _REPO_ROOT / "phase1" / "dataset" / "synthetic.jsonl"
FIXTURES_ROOT = _REPO_ROOT / "fixtures"
REPO = "synthetic"
SYNTHETIC_CASES = ["syn_001", "syn_002", "syn_003", "syn_004", "syn_005"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_case(case_id: str) -> dict:
    with open(JSONL_PATH) as f:
        for line in f:
            if line.strip():
                case = json.loads(line)
                if case["id"] == case_id:
                    return case
    raise ValueError(f"Case {case_id!r} not found in synthetic.jsonl")



def _ensure_fixture_repo(fixture_path: Path) -> None:
    """Init fixture as git repo if conftest.py hasn't done it yet."""
    if (fixture_path / ".git").exists():
        return
    import subprocess
    git = ["git", "-C", str(fixture_path)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "challayagneshsaisiddhardha@gmail.com"], check=True)
    subprocess.run([*git, "config", "user.name", "CH Y SAI SIDDHARDHA"], check=True)
    subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
    subprocess.run([*git, "config", "core.eol", "lf"], check=True)
    (fixture_path / ".gitattributes").write_text("* text eol=lf\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init buggy state"], check=True)


# ---------------------------------------------------------------------------
# Security + Complexity Helpers (C1)
# ---------------------------------------------------------------------------

def _run_bandit_check(diff: str, fixture_path: Path, affected_file: str) -> str:
    """
    Run bandit security scan on the affected file (after patch content is known).
    Returns issue summary string on fail, empty string on pass or tool not available.
    Never raises.
    """
    import tempfile

    try:
        # Write patch to a temp file for analysis
        # Bandit scans the file content — extract added lines from diff
        added_lines: list[str] = [
            line[1:] for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        if not added_lines:
            return ""

        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write("\n".join(added_lines))
            tmp_path = tmp.name

        result = subprocess.run(
            [sys.executable, "-m", "bandit", "-q", tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        Path(tmp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            return result.stdout[:500] or result.stderr[:500]
    except FileNotFoundError:
        log.warning("bandit.not_installed")
    except Exception as exc:
        log.warning("bandit.error", error=str(exc))

    return ""


def _run_radon_check(diff: str, fixture_path: Path, affected_file: str) -> str:
    """
    Run radon complexity check on patched lines.
    Returns complexity detail if high complexity detected, empty string otherwise.
    Never raises.
    """
    import tempfile

    try:
        added_lines: list[str] = [
            line[1:] for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
        if not added_lines:
            return ""

        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write("\n".join(added_lines))
            tmp_path = tmp.name

        result = subprocess.run(
            [sys.executable, "-m", "radon", "cc", tmp_path, "-s", "--min", "C"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        Path(tmp_path).unlink(missing_ok=True)

        if result.returncode == 0 and result.stdout.strip():
            # Any output at --min C means complexity C or above (10+)
            return result.stdout[:500]
    except FileNotFoundError:
        log.warning("radon.not_installed")
    except Exception as exc:
        log.warning("radon.error", error=str(exc))

    return ""


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run(case_id: str) -> MemoryEntry:
    """
    Run the full repair pipeline for one synthetic case.

    Stages (strict order per CLAUDE.md):
    Observer → LogParser → RegexClassifier → PreSafetyGate
    → ThompsonSampler.sample() → ContextBuilder → Agent-Y Reasoner
    → DeepSeekWorker → PostSafetyValidation → Executor
    → RegressionCheck → DecisionEngine → ThompsonSampler.update() → MemoryStore

    try/finally guarantees MemoryStore write on every run. (P8)
    """
    # ThompsonSampler — lazy import inside function (B13 / env var rule)
    from phase2.strategy.thompson import ThompsonSampler
    sampler = ThompsonSampler()

    run_id = str(uuid.uuid4())[:8]
    start_time = time.monotonic()
    fixture_path = FIXTURES_ROOT / case_id

    outcome = build_default_entry(run_id=run_id, repo=REPO)
    outcome = outcome.model_copy(update={"bug_signature": f"{REPO}:unknown:unknown:{case_id}"})

    try:
        log.info("pipeline.start", case_id=case_id, run_id=run_id)

        # 1 — Observer
        case = _load_case(case_id)
        error_lines: list[str] = case["error_log"]

        # 2 — LogParser
        cleaned = clean_and_extract(error_lines)
        if not cleaned:
            cleaned = error_lines  # fallback — use raw lines

        # 3 — RegexClassifier
        classifier_result = classify_with_fallback(cleaned, repo=REPO)
        outcome = outcome.model_copy(update={
            "failure_category": classifier_result.category,
            "bug_signature": classifier_result.bug_signature,
            "confidence_score": classifier_result.confidence,
        })

        # 4 — PreSafetyGate
        gate = gate_check(classifier_result)
        outcome = outcome.model_copy(update={"mode": gate.mode})

        if not gate.passed:
            log.info("pipeline.observer_mode", case_id=case_id, reason=gate.reason)
            outcome = outcome.model_copy(update={"decision": "abstained"})
            return outcome

        # 4.3 — Gateway stage (C2): zero-cost direct fixes for known patterns
        from phase2.gateway import check as gateway_check
        _ensure_fixture_repo(fixture_path)
        rollback(fixture_path)
        gw_result = gateway_check(cleaned, fixture_path)
        if gw_result and gw_result.success:
            log.info("gateway.hit", case_id=case_id, rule=gw_result.matched_rule)
            gw_after: TestReport = run_tests(fixture_path)
            if gw_after.passed:
                outcome = outcome.model_copy(update={
                    "patch_applied": gw_result.patch_applied,
                    "decision": "accepted",
                    "sandbox_result": "pass",
                    "model_used": "gateway",
                    "test_summary": f"{gw_after.total} total, {len(gw_after.failed_tests)} failed",
                })
                sampler.update(classifier_result.bug_signature, accepted=True)
                rollback(fixture_path)
                return outcome
            log.warning("gateway.tests_failed", case_id=case_id, rule=gw_result.matched_rule)
        rollback(fixture_path)

        # 4.5 — Memory Reuse Bypass (C0): skip full pipeline for known bugs
        from phase2.memory.similarity import MemoryEngine
        engine = MemoryEngine()
        cached = engine.find_similar(
            classifier_result.bug_signature,
            classifier_result.affected_file,
        )
        if cached:
            log.info(
                "memory.reuse",
                case_id=case_id,
                score=cached["match_score"],
                sig=cached["metadata"]["bug_signature"],
            )
            _ensure_fixture_repo(fixture_path)
            rollback(fixture_path)
            reuse_result = apply_patch(cached["patch"], fixture_path)
            if reuse_result.success:
                after_reuse: TestReport = run_tests(fixture_path)
                if after_reuse.passed:
                    outcome = outcome.model_copy(update={
                        "patch_applied": cached["patch"],
                        "decision": "accepted",
                        "sandbox_result": "pass",
                        "model_used": "memory_reuse",
                        "test_summary": f"{after_reuse.total} total, {len(after_reuse.failed_tests)} failed",
                    })
                    sampler.update(classifier_result.bug_signature, accepted=True)
                    rollback(fixture_path)
                    return outcome
            # Reuse failed — fall through to full pipeline
            log.warning("memory.reuse.failed", case_id=case_id)
            rollback(fixture_path)

        # Thompson Sampling: score this arm before attempting fix
        exploration_score = sampler.sample(classifier_result.bug_signature)
        log.info(
            "thompson.exploration_score",
            case_id=case_id,
            bug_signature=classifier_result.bug_signature,
            exploration_score=round(exploration_score, 4),
        )

        # 5 — ContextBuilder (v1.1 — enriched with RAG)
        _ensure_fixture_repo(fixture_path)
        rollback(fixture_path)  # ensure clean state
        context = build_context(classifier_result, fixture_path, error_lines=cleaned)

        # 5.5 — Agent-Y Reasoner (optional — fallback to raw context on failure)
        try:
            reasoner_output = reason(context, classifier_result)
            log.info(
                "reasoner.ok",
                case_id=case_id,
                strategy=reasoner_output.strategy[:80],
                confidence=reasoner_output.confidence,
            )
            enriched_context = context + "\n\nSTRATEGY: " + reasoner_output.strategy
        except (ReasonerError, EnvironmentError) as exc:
            log.warning("reasoner.fallback", case_id=case_id, error=str(exc))
            enriched_context = context  # Agent-X baseline — pipeline continues

        # 6 — Run tests BEFORE patch (regression baseline)
        before: TestReport = run_tests(fixture_path)

        # 7 — DeepSeekWorker (includes PostSafetyValidation + retry internally)
        worker_result = generate_patch(
            error_lines=cleaned,
            classifier_result=classifier_result,
            context=enriched_context,
        )
        diff = worker_result.diff
        outcome = outcome.model_copy(update={
            "patch_applied": diff,
            "lines_changed": worker_result.sanitiser_result.line_count,
            "model_used": worker_result.model_used,
            "retries_used": worker_result.attempt - 1,
        })

        # 7.1 — Structural escalation: sanitiser rejected all retries
        if not worker_result.sanitiser_result.passed and worker_result.attempt >= 3:
            log.warning(
                "decision.structural",
                case_id=case_id,
                reason="exceeded line limit on all retries",
            )
            outcome = outcome.model_copy(update={"decision": "structural"})
            sampler.update(classifier_result.bug_signature, accepted=False, penalty=5)
            return outcome

        # 7.2 — Bandit security gate (PostSafetyValidation)
        _bandit_reject = _run_bandit_check(diff, fixture_path, classifier_result.affected_file)
        if _bandit_reject:
            log.warning("security.bandit_fail", case_id=case_id, issues=_bandit_reject)
            outcome = outcome.model_copy(update={
                "decision": "rejected",
                "rejection_reason": "security_issue",
                "error": f"bandit: {_bandit_reject}",
            })
            return outcome

        # 7.3 — Radon complexity check
        _radon_risk = _run_radon_check(diff, fixture_path, classifier_result.affected_file)
        if _radon_risk:
            log.warning("doctor.architecture_risk", case_id=case_id, complexity=_radon_risk)
            outcome = outcome.model_copy(update={"decision": "structural"})
            sampler.update(classifier_result.bug_signature, accepted=False, penalty=5)
            return outcome

        # 8 — Executor: git apply
        apply_result = apply_patch(diff, fixture_path)

        if not apply_result.success:
            log.warning("pipeline.patch_failed", case_id=case_id, error=apply_result.error)
            outcome = outcome.model_copy(update={
                "decision": "rejected",
                "rejection_reason": "prompt_issue",
                "sandbox_result": "fail",
                "error": apply_result.error,
            })
            return outcome

        # 8.5 — Syntax Reflex: ast.parse() for .py files before spinning up pytest
        syntax_error = check_syntax(fixture_path, classifier_result.affected_file)
        if syntax_error:
            rollback(fixture_path)
            log.warning("pipeline.syntax_error", case_id=case_id, error=syntax_error)
            outcome = outcome.model_copy(update={
                "decision": "rejected",
                "rejection_reason": "prompt_issue",
                "sandbox_result": "fail",
                "error": syntax_error,
            })
            return outcome

        # 9 — RegressionCheck (multi-run stable: all 3 runs must pass)
        after: TestReport = run_tests_stable(fixture_path)
        if after.note == "flaky":
            rollback(fixture_path)
            log.warning("executor.flaky", case_id=case_id)
            outcome = outcome.model_copy(update={"decision": "abstained", "error": "flaky"})
            return outcome

        regression = check_regression(before, after)
        outcome = outcome.model_copy(update={
            "regression_introduced": regression,
            "sandbox_result": "pass" if after.passed else "fail",
        })

        if regression:
            rollback(fixture_path)
            log.warning("pipeline.regression", case_id=case_id)
            outcome = outcome.model_copy(update={"decision": "escalated"})
            return outcome

        # 10 — DecisionEngine
        outcome = outcome.model_copy(update={
            "test_summary": f"{after.total} total, {len(after.failed_tests)} failed",
        })
        if after.passed:
            outcome = outcome.model_copy(update={"decision": "accepted"})
            log.info("pipeline.accepted", case_id=case_id)
        else:
            outcome = outcome.model_copy(update={
                "decision": "rejected",
                "rejection_reason": "logic_issue",
            })
            log.warning("pipeline.rejected", case_id=case_id)

        # 10.5 — Thompson update: feed outcome back to sampler
        sampler.update(
            classifier_result.bug_signature,
            accepted=(outcome.decision == "accepted"),
        )

        # Rollback fixture so it stays clean for re-runs
        rollback(fixture_path)

    except Exception as e:
        log.error("pipeline.exception", case_id=case_id, error=str(e))
        outcome = outcome.model_copy(update={
            "decision": "abstained",
            "error": str(e),
        })
        try:
            rollback(fixture_path)
        except Exception:
            pass

    finally:
        # P8 — ALWAYS write to memory, no exceptions
        elapsed = time.monotonic() - start_time
        outcome = outcome.model_copy(update={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mttr_seconds": round(elapsed, 2),
        })
        append(outcome)
        log.info(
            "pipeline.done",
            case_id=case_id,
            run_id=run_id,
            decision=outcome.decision,
            mttr=outcome.mttr_seconds,
        )

    return outcome


# ---------------------------------------------------------------------------
# Run all 5 synthetic cases
# ---------------------------------------------------------------------------

def run_all_synthetic() -> list[MemoryEntry]:
    """Run the full pipeline on all 5 synthetic cases and print a summary."""
    case_ids = SYNTHETIC_CASES
    results: list[MemoryEntry] = []

    print("\n" + "=" * 70)
    print("Agent-X v1 — Synthetic Pipeline Run")
    print("=" * 70)

    header = f"{'Case':<10} {'Category':<18} {'Decision':<12} {'Conf':>6} {'Lines':>6} {'MTTR':>7}"
    print(header)
    print("-" * 70)

    for case_id in case_ids:
        entry = run(case_id)
        results.append(entry)

        icon = "PASS" if entry.decision == "accepted" else "FAIL"
        print(
            f"{icon} {case_id:<9} {entry.failure_category:<18} "
            f"{entry.decision:<12} {entry.confidence_score:>6.2f} "
            f"{entry.lines_changed:>6} {entry.mttr_seconds:>6.1f}s"
        )

    print("=" * 70)
    accepted = sum(1 for r in results if r.decision == "accepted")
    print(f"Result: {accepted}/5 accepted | memory.jsonl has {len(results)} entries")
    print("=" * 70 + "\n")

    return results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single case mode
        entry = run(sys.argv[1])
        print(f"\nResult: {entry.decision} | confidence={entry.confidence_score:.2f} | mttr={entry.mttr_seconds}s")
    else:
        run_all_synthetic()
