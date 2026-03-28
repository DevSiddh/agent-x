# Agent-X v2.3 | Steps E0-E2 — Analytics Layer
# $0 cost — all three run on existing data, no new APIs, no GPU
# Last updated: 2026-03-22
# Prerequisite sequence: AUDIT → C3b → D0 → D1 → E0 → E1 → E2

---

## STEP E0 — Dashboard (Streamlit)
# Prerequisite: AUDIT DONE. 101+ entries already in memory.jsonl.
# Cost: $0 — reads existing files, no API calls.

```
You are building a local Streamlit dashboard for Agent-X.
Read CLAUDE.md, docs/progress.md before touching anything.
Step AUDIT must be DONE. Do not break existing tests.

FILE: phase3/dashboard.py

WHAT IT SHOWS (5 panels):

Panel 1 — Run Summary (top row, 4 metrics)
  total_runs | accepted | rejected | abstained
  Read from memory.jsonl — count each decision field

Panel 2 — Thompson Arm Scores (table)
  Load thompson_state.json → for each arm:
    arm_name | alpha | beta | win_rate = alpha/(alpha+beta) | total_runs = alpha+beta
  Sort by win_rate descending
  Highlight rows where win_rate > 0.80 (green) or < 0.50 (red)

Panel 3 — Recent Runs (last 20, scrollable table)
  Columns: timestamp | repo | category | decision | confidence | model_used
  Read last 20 lines of memory.jsonl

Panel 4 — Cost Saved (single number)
  gateway_hits = count(model_used == "gateway") in memory.jsonl
  memory_reuse_hits = count(model_used == "memory_reuse") in memory.jsonl
  LLM_COST_PER_CALL = 0.002  # estimated DeepSeek cost per run
  cost_saved = (gateway_hits + memory_reuse_hits) * LLM_COST_PER_CALL
  Display: "Gateway + memory reuse saved ${cost_saved:.2f} in API calls"

Panel 5 — Category Breakdown (bar chart)
  Count accepted runs per category (DependencyError, RuntimeError, etc.)
  Use st.bar_chart() — no matplotlib needed

IMPLEMENTATION RULES:
- streamlit only — no Flask, no FastAPI, no database
- Read memory.jsonl line by line (never load all into RAM at once)
- Auto-refresh every 30s: st.empty() + time.sleep(30) + st.rerun()
- Type hints, structlog at module level, __main__ smoke test
- Never modifies memory.jsonl or thompson_state.json — read only

HOW TO RUN:
  streamlit run phase3/dashboard.py

tests/test_dashboard.py:
- Test parse_memory() returns correct counts for all 4 decisions
- Test parse_thompson() returns win_rate = alpha/(alpha+beta)
- Test cost_saved calculation correct (gateway_hits × 0.002)
- Test parse_memory handles empty file without raising
- Test parse_memory handles corrupt line without raising (skip and continue)

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- Dashboard runs locally: streamlit run phase3/dashboard.py
- All 5 panels show real data from memory.jsonl
- docs/progress.md updated: Step E0 DONE
```

---

## STEP E1 — Failure Learning (Rejection Reason Classifier)
# Prerequisite: AUDIT DONE. memory.jsonl already has 101+ entries including rejections.
# Build IMMEDIATELY after AUDIT — before C3b. Earlier = better data for all subsequent steps.
# Cost: $0 — pure regex on existing data, no LLM calls.
# Why early: E1 tells you WHICH pipeline stage to fix next. That informs C3b, D0, D1 scope.

```
You are building a rejection reason classifier for Agent-X.
Read CLAUDE.md, docs/progress.md before touching anything.
Step AUDIT must be DONE. Do not break existing tests.

FILE: phase2/memory/failure_classifier.py

PURPOSE:
Read all rejected entries from memory.jsonl → classify WHY they were rejected
→ output a pattern report so you know which part of the pipeline to improve.

REJECTION CATEGORIES (classify from rejection_reason field):

  Category A — "prompt_issue" (patch format was wrong)
    Patterns: "diff header missing", "+++ header", "missing ---", "no unified diff"
    Root cause: DeepSeek ignored format instructions
    Fix direction: harden system prompt, add format example

  Category B — "context_issue" (wrong file or path)
    Patterns: "wrong file path", "file not found", "path mismatch", "affected_file"
    Root cause: context_builder gave wrong file path
    Fix direction: fix context_builder file resolution

  Category C — "logic_issue" (patch applied but tests still fail)
    Patterns: "tests still fail", "regression", "new failures", "test_failure"
    Root cause: patch was syntactically valid but logically wrong
    Fix direction: improve Agent-Y strategy or raise retry count

  Category D — "size_issue" (patch too long)
    Patterns: "exceeds", "too many lines", "15 lines", "line count"
    Root cause: DeepSeek generated patch beyond 15-line cap
    Fix direction: narrow prompt scope, split into smaller tasks

  Category E — "security_issue" (detect-secrets or pip-audit rejected)
    Patterns: "hardcoded secret", "CVE-", "vulnerability"
    Root cause: patch contained credential or vulnerable dep
    Fix direction: add explicit "no hardcoded values" to system prompt

  Category F — "unknown" (none of above match)
    Log the raw rejection_reason for manual review

class RejectionSummary(BaseModel):
    total_rejected: int
    by_category: dict[str, int]          # {"prompt_issue": 12, "logic_issue": 8, ...}
    by_category_pct: dict[str, float]    # percentage of total rejected
    unknown_reasons: list[str]           # raw strings that didn't match — for manual review
    top_issue: str                       # category with highest count
    recommendation: str                  # one sentence: what to fix first

def classify_rejections(memory_path: Path) -> RejectionSummary:
    """
    Read memory.jsonl → filter decision == "rejected" → classify each entry.

    TWO-PATH classification (handle both old and new entries):
      Path 1 — rejection_reason already set (new entries, post pipeline.py update):
        if entry["rejection_reason"] in VALID_CATEGORIES → use it directly, no regex
        VALID_CATEGORIES = {"logic_issue","security_issue","prompt_issue",
                            "size_issue","context_issue","flaky"}

      Path 2 — rejection_reason == "" (old entries, pre pipeline.py update):
        classify from entry["error"] field using regex patterns below
        write result into in-memory record only — never modify memory.jsonl

    Return RejectionSummary with counts + percentages + recommendation.
    """

def print_report(summary: RejectionSummary) -> None:
    """
    Print human-readable report to stdout:
    === Rejection Analysis ===
    Total rejected: 23
    Top issue: prompt_issue (52%)
    Recommendation: Harden system prompt — add explicit diff format example
    ...
    """

__main__ block: run classify_rejections(MEMORY_PATH) → print_report()

tests/test_failure_classifier.py:
- Test "diff header missing" → classified as prompt_issue
- Test "wrong file path" → classified as context_issue
- Test "tests still fail" → classified as logic_issue
- Test "exceeds 15 lines" → classified as size_issue
- Test "CVE-2024-1234" → classified as security_issue
- Test unrecognised reason → classified as unknown, added to unknown_reasons
- Test empty memory.jsonl → returns RejectionSummary with zeros, never raises
- Test top_issue returns correct highest-count category

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- python phase2/memory/failure_classifier.py → prints report on real memory.jsonl
- Report shows top_issue + recommendation
- docs/progress.md updated: Step E1 DONE
```

---

## STEP E2 — Cross-Repo Pattern Detection (Auto Gateway Rules)
# Prerequisite: D1 DONE. Needs real cross-repo data (multi-repo runs).
# Gate: 3+ different repos in memory.jsonl with overlapping bug_signatures.
# Cost: $0 — pure analytics on memory.jsonl, no LLM calls.

```
You are building cross-repo pattern detection for Agent-X.
Read CLAUDE.md, docs/progress.md before touching anything.
Step D1 must be DONE. Do not break existing tests.

PREREQUISITE CHECK:
Count distinct repos in memory.jsonl.
If < 3 distinct repos → STOP. Not enough cross-repo data yet.
Print: "Gate not met: only N repos in memory. Need 3+."

FILE: phase2/memory/pattern_detector.py

PURPOSE:
Find bug patterns that appear across multiple repos with high acceptance rate
→ auto-generate gateway rules for zero-cost fixes.

ALGORITHM:

Step 1 — Build signature table
  For each entry in memory.jsonl:
    Extract: bug_type (e.g. "ModuleNotFoundError"), keyword, repo, decision
    Group by (bug_type, keyword) — NOT by full bug_signature (which includes repo)

Step 2 — Filter cross-repo patterns
  Keep only groups where:
    distinct_repos >= 3        (appears in 3+ different repos)
    acceptance_rate >= 0.80    (80%+ of runs accepted)
    total_runs >= 5            (enough signal — not just 3 lucky runs)

Step 3 — Generate gateway rule candidates
  For each qualifying pattern:
    rule_id = f"auto_{bug_type}_{keyword}".lower().replace(" ", "_")
    match_pattern = regex derived from keyword (escape special chars)
    suggested_fix = most common patch text among accepted entries for this pattern
    confidence = acceptance_rate

class PatternCandidate(BaseModel):
    rule_id: str
    bug_type: str
    keyword: str
    distinct_repos: int
    total_runs: int
    acceptance_rate: float
    suggested_fix: str         # most common accepted patch for this pattern
    match_pattern: str         # regex ready to add to gateway.py

def detect_patterns(memory_path: Path) -> list[PatternCandidate]:
    """
    Read memory.jsonl → group by (bug_type, keyword) → filter → return candidates
    Never raises. Returns [] if gate not met.
    """

def print_candidates(candidates: list[PatternCandidate]) -> None:
    """
    Print human-readable report:
    === Cross-Repo Pattern Candidates ===
    Found 2 patterns ready for gateway promotion:

    [1] rule_id: auto_modulenotfounderror_setuptools
        Pattern: "No module named 'setuptools'"
        Repos:   12 distinct repos
        Win rate: 94%
        Fix:     append 'setuptools' to requirements.txt
        → Add to gateway.py? (manual review required before adding)
    """

__main__ block: run detect_patterns(MEMORY_PATH) → print_candidates()

tests/test_pattern_detector.py:
- Test pattern with 5 repos + 90% acceptance → included in candidates
- Test pattern with 2 repos → excluded (below distinct_repos threshold)
- Test pattern with 3 repos + 70% acceptance → excluded (below acceptance_rate)
- Test pattern with 3 repos + 80% acceptance + 4 runs → excluded (below total_runs)
- Test suggested_fix returns most common patch text
- Test empty memory.jsonl → returns [], never raises
- Test single-repo entries → never appear in candidates

NOTE: Candidates are printed for MANUAL REVIEW — never auto-written to gateway.py.
Human reviews each candidate, decides to add or reject. This is not auto-overwrite.

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- python phase2/memory/pattern_detector.py → prints candidates on real memory.jsonl
- Gate check works: stops cleanly if < 3 repos
- docs/progress.md updated: Step E2 DONE
```
