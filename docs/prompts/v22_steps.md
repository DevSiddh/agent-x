# Agent-X v2.2 | Steps D0-D1 (PENDING — after C2)
# Context Tools for Agent-Y/X + Auto-PR
# Last updated: 2026-03-22

---

## STEP D0 — v2.2 Context Tools + GitHub file fetch fix
# Prerequisite: v2.1.5 DONE (C0-C2). Build after memory engine is stable.
# Fixes P23 (no architecture understanding) + P20-partial (file_missing on real runs).

```
You are building Agent-X/Y v2.2 context tools.
Read CLAUDE.md, docs/progress.md before touching anything.
Steps C0-C2 must be DONE. Do not break existing tests.

All tools: phase2/tools/ — one file per tool, one test file per tool.
All tools: 200KB cap, structlog, lazy imports, type hints, __main__ smoke test.
All tools plug into ContextBuilder only — no other file changes.

BUILD IN THIS ORDER:

0a. Negative Test Check + Shadow Type Check in regression.py (R1/L2 solution — silent killer fix)
    File: phase2/executor/regression.py
    Add to apply_patch() BEFORE accepting any fix:

    Step 1 — Verify failure (pre-patch):
      run specific failing test on BROKEN code → must FAIL
      if it passes → log.warning("regression.weak_test") → escalate, do NOT patch
      extract test name from the CI log failure line — pass it to pytest -k

    Step 2 — Verify fix (post-patch):
      run specific failing test on PATCHED code → must PASS

    Step 3 — Shadow type check:
      subprocess: python -m mypy --check-untyped-defs {patched_file} --no-error-summary
      if mypy exit code != 0 → log.warning("regression.type_violation") → reject patch
      Skip silently if mypy not installed (never raises)

    Step 4 — Full regression: existing run_tests_stable() — no new failures

    Tests: test_negative_check_rejects_placebo, test_type_check_catches_wrong_return,
           test_mypy_missing_skips_gracefully, test_full_sequence_passes_good_patch

0b. Security gate — phase2/executor/security_gate.py (D12 solution)
    Sequential, fail-fast, scan patch not repo:

    class SecurityResult(BaseModel):
        passed: bool
        reason: str = ""   # rejection reason injected into retry prompt

    def scan_patch(patch: str, requirements_modified: bool) -> SecurityResult:
        """
        Step 1 — Secret scan (<0.5s):
          Write patch to temp file → subprocess detect-secrets scan {tmp}
          if secrets found → return SecurityResult(passed=False, reason="hardcoded secret...")

        Step 2 — CVE check (~2s, conditional):
          if requirements_modified:
              subprocess pip-audit -r requirements.txt --format json
              if CVE found → return SecurityResult(passed=False, reason="CVE-XXXX in {pkg}...")

        Never raises. If tool not installed → log warning, return passed=True (never blocks).
        """

    Wire into pipeline.py after sanitiser, before executor.apply_patch():
      security_result = scan_patch(patch, requirements_modified)
      if not security_result.passed:
          log.warning("security.rejected", reason=security_result.reason)
          outcome = outcome.model_copy(update={"decision": "rejected",
                                               "rejection_reason": security_result.reason})
          return outcome  # reason goes into retry prompt automatically

    Tests: test_secret_in_patch_rejected, test_cve_in_requirements_rejected,
           test_clean_patch_passes, test_missing_tool_never_blocks

0c. Monitoring layer in phase3/runner.py (I2 solution)
    Add to poll_loop() — 3 lines total:
      End of every successful iteration: requests.get(HEALTHCHECK_URL, timeout=5) if env set
      On fatal error (token expired, DB locked): requests.post(ntfy.sh/{NTFY_TOPIC}, data=msg)
    Add HEALTHCHECK_URL and NTFY_TOPIC to .env.example (empty values)
    Never raises — wrap in try/except, log on failure, continue loop

0c. Fix context_builder.file_missing (P23 blocker — affects every real run)
   - Problem: affected_file is /home/runner/work/... — path doesn't exist locally
   - Fix: fetch file content from GitHub API before building context
   - In phase2/context_builder.py build_context():
     Try local path first → if missing, call fetch_file_from_github(repo, path, run_id)
   - phase2/tools/github_file.py
     fetch_file(repo: str, path: str, ref: str = "main") -> str | None
       GET /repos/{repo}/contents/{path}?ref={ref}
       Decode base64 content, return as string
       Return None on 404 — never raises
       GITHUB_TOKEN lazy inside function
   - Test: mock GitHub API, assert content returned and injected into context

1. phase2/tools/ast_mapper.py  (replaces tree_reader.py — depth=3 fails monorepos)
   - map_repo(repo: Path, max_tokens: int = 2000) -> str
     Use ast module (stdlib, no tree-sitter dependency) to extract signatures only:
       - class names + method signatures (no bodies)
       - top-level function signatures (no bodies)
       - module docstring (first line only)
     Output format:
       src/auth/token.py:
           class TokenValidator:
               def validate(jwt: str) -> bool
       src/billing/invoice.py:
               def generate_invoice(user_id: int) -> dict
     Exclude: .git/, __pycache__/, node_modules/, *.pyc, test files
     Hard cap: stop adding files once output exceeds max_tokens (2000)
     Sort by: files closest to affected_file first (most relevant first)
     Never raises. Returns empty string if ast parse fails on any file.
   - Use: Agent-Y sees full architecture skeleton in ~2000 tokens
     Replaces naive depth=3 tree that explodes on monorepos (150k+ tokens)

   phase2/tools/blast_radius.py  (NEW — dependency graph pruning)
   - get_blast_radius(repo: Path, affected_file: Path) -> list[Path]
     Parse imports of affected_file using ast module:
       Tier 1: affected_file itself (always included)
       Tier 2: files imported BY affected_file (direct dependencies)
       Tier 3: files that import affected_file (upstream consumers)
     Return list of Paths — caller reads full content of these files only
     Max 8 files total — if more, take closest by import depth
     Supports Python (.py) now. JS/Java import parsing: stub for now, extend at C3b.
   - Use: context_builder reads full content ONLY for blast radius files
     ~4 files × 500 tokens = ~2000 tokens vs 150k+ for full monorepo

2. phase2/tools/web_reader.py
   - fetch_docs(url: str, max_tokens: int = 2000) -> str
     httpx GET, BeautifulSoup parse
     Strip: nav, footer, ads, scripts, duplicate content
     Return clean text, max 2 pages, max 2000 tokens
   - Use: Agent-Y reads current API docs before planning
     Fixes outdated LLM knowledge for fast-moving APIs
   - Agent-Y ONLY

   CONDITIONAL WEB FALLBACK (Zero-Day trigger — wire into context_builder.py):
   When find_for_rag() returns [] (FinalScore < 0.55 for all entries):
     if failure_category in ("DependencyError", "EnvironmentError"):
         query = f"{category} {matched_pattern} {keyword} site:github.com OR site:stackoverflow.com"
         docs = fetch_docs(build_search_url(query), max_tokens=1000)
         if docs:
             sections.append(f"## Web Reference (live docs — local memory empty)\n{docs}")
             log.info("context_builder.web_fallback", query=query)
   Gate: only fires when local RAG returns nothing (< 0.55 threshold)
   Budget: ~$0.02 per call — only paid when local memory can't help
   Flywheel: patch accepted → written to memory.jsonl → next time costs $0
   Requires: TAVILY_API_KEY or GitHub Issues API scraper (lazy, inside function)
   Never raises. If fetch fails → log warning, continue without web context.

3. phase2/tools/github_search.py
   - search_code(query: str, language: str = "") -> list[str]
     GitHub API (GITHUB_TOKEN lazy inside function)
     Filter: stars > 50, recent commits, language match
     Return 2-3 small relevant snippets only
   - Use: Agent-X gets real-world fix examples for obscure errors
   - Agent-X ONLY

4. phase2/tools/pdf_extractor.py  <- NotebookLM-style summarizer
   - summarize_docs(path: Path) -> str
     pdfplumber extracts raw text (cap at 200KB)
     LLM call (deepseek-chat) summarizes into structured output:
       what_it_does, key_endpoints, authentication, rate_limits, key_params
     Returns clean structured summary — NEVER raw PDF dump
   - Only trigger when task contains "API" OR "SDK" OR user uploads PDF
   - Agent-Y ONLY

tests/test_tools.py — one test file covers all tools:
- Test fetch_file returns content, handles 404 gracefully
- Test ast_mapper returns only signatures, not function bodies
- Test ast_mapper respects max_tokens cap (stops adding files)
- Test blast_radius returns 3 tiers: affected + imports + importers
- Test blast_radius max 8 files even on highly connected file
- Test blast_radius returns [affected_file] if no imports found
- Test fetch_docs strips noise, respects token limit
- Test github_search filters by stars + language
- Test summarize_docs returns structured dict, never raw dump
- Test each tool handles failure gracefully (never raises)

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- context_builder no longer logs file_missing on real GitHub runs
- ContextBuilder uses ast_mapper (skeleton) + blast_radius (full content) for Agent-Y
- ContextBuilder uses github_search + RAG for Agent-X
- ast_mapper output stays under 2000 tokens on any repo
- blast_radius never exceeds 8 files
- pdf summarizer produces structured output on a real PDF
- docs/progress.md updated: Step D0 DONE
```

---

## STEP D1 — Auto-PR + Structural Escalation Issues + Transparent Expert Layer
# Prerequisite: D0 DONE. Gate: 101+ accepted runs (ALREADY UNLOCKED as of 2026-03-22).
# Fixes P20 (patch accepted locally but repo stays broken).
# Also fixes: structural decisions silently buried — now become GitHub issues.
# Also adds: Transparent Expert layer — diagnosis + complexity delta in every PR.

```
You are building the auto-PR feature for Agent-X v2.2.
Read CLAUDE.md, docs/progress.md before touching anything.
Step D0 must be DONE. Do not break existing tests.

PART 0 — TRANSPARENT EXPERT LAYER (build before pr_creator.py)

0a. Update Agent-Y output schema — add diagnosis field
    File: agent_y/reasoner.py

    Current ReasonerOutput schema:
      strategy: str, files_to_change: list[str], confidence: float, reasoning: str

    Add ONE field:
      diagnosis: str   # 1 sentence — what is broken and why
                       # e.g. "ZeroDivisionError in utils.py caused by missing
                       #        empty-list guard before division on line 42"

    Update Agent-Y system prompt — add to JSON output instruction:
      "diagnosis": "one sentence: what is broken and why (plain English, no jargon)"

    Cost: ~50 extra tokens per run. Agent-Y call is already paid for.
    Validate in validate_strategy(): diagnosis must be non-empty string, max 200 chars.
    Wire diagnosis through pipeline.py → store in MemoryEntry → pass to pr_creator.py

0b. Add complexity delta to regression.py
    File: phase2/executor/regression.py

    def get_complexity(file_path: Path) -> float | None:
        """Run radon cc {file_path} --average — return average complexity score.
           Return None if radon not installed or file not Python. Never raises."""

    Call BEFORE applying patch → store as complexity_before
    Call AFTER applying patch → store as complexity_after
    Add to TestReport:
      complexity_before: float | None
      complexity_after: float | None
      complexity_delta: float | None   # after - before, positive = more complex

    If complexity_delta > 2.0:
        log.warning("regression.complexity_increase", delta=complexity_delta)
        # Does NOT reject — warns only. Human decides in PR review.

    Radon already installed (used in C1 gate). Zero new dependency.

AUTHENTICATION: GitHub App (not PAT — PAT fails enterprise SOC2)
  Required env vars (lazy inside functions):
    GITHUB_APP_ID              ← app registration ID
    GITHUB_APP_PRIVATE_KEY     ← .pem key content (multiline env var)
    GITHUB_APP_INSTALLATION_ID ← per-repo installation ID
  Generate installation token:
    POST /app/installations/{installation_id}/access_tokens
    → short-lived token (1hr), bot commits show as "agent-x[bot]" not your name

FILE: phase2/tools/pr_creator.py

class PRResult(BaseModel):
    pr_url: str
    branch: str
    pr_number: int
    success: bool

class IssueResult(BaseModel):
    issue_url: str
    issue_number: int
    success: bool

def create_pr(
    repo: str,           # "owner/repo"
    patch: str,          # raw unified diff
    affected_file: str,  # relative path in repo
    run_id: str,
    bug_signature: str,  # for branch name
    category: str,
    test_summary: str,
    original_author: str | None,  # from webhook payload — assign as reviewer
) -> PRResult | None:
    """
    Enterprise-safe flow (Git Database API — no local git clone needed):

    1. Get installation token (GitHub App auth)
    2. GET /repos/{repo}/git/ref/heads/main → get latest SHA
    3. GET /repos/{repo}/git/commits/{sha} → get tree SHA
    4. GET /repos/{repo}/contents/{affected_file} → get current blob
    5. Apply patch to blob content in memory
    6. POST /repos/{repo}/git/blobs → create new blob with patched content
    7. POST /repos/{repo}/git/trees → create new tree with updated blob
    8. POST /repos/{repo}/git/commits → create signed commit (auto-verified)
    9. POST /repos/{repo}/git/refs → create branch: agent-x-fixes/{bug_sig_hash}
    10. POST /repos/{repo}/pulls
        title: "[agent-x] fix {category} — {affected_file}"
        body: audit receipt (see below)
        draft: true           ← ALWAYS draft — human must mark ready + merge
        head: agent-x-fixes/{bug_sig_hash}
    11. If original_author: POST /repos/{repo}/pulls/{number}/requested_reviewers
        → assigns original commit author immediately

    PR body (audit receipt — Transparent Expert format):
        ## Agent-X Automated Fix
        **Diagnosis:** {diagnosis}
        **Category:** {category}
        **File:** {affected_file}
        **Run ID:** {run_id}
        **Test result:** {test_summary}
        **Confidence:** {confidence}
        **Complexity:** {complexity_before:.1f} → {complexity_after:.1f}
          ({complexity_delta:+.1f} — ⚠️ increased complexity, review carefully if > +2.0)
        ### Proof (Ghost Test)
        The failing CI test: `{failing_test_name}`
        - ❌ Fails on original code (verified pre-patch)
        - ✅ Passes with this fix (verified post-patch)
        ### Diff
        ```diff
        {patch}
        ```
        ### What to review
        - Does the diagnosis above match what you see in the diff?
        - Is complexity increase (if any) acceptable?
        - Are there other files that depend on this change?
        > This PR was opened in Draft mode. Review the diff, run tests locally,
        > then mark Ready for Review. Agent-X never merges automatically.

    Return PRResult or None on any failure. Never raises.
    """

def open_structural_issue(
    repo: str,
    run_id: str,
    category: str,
    affected_file: str,
    reason: str,
    original_author: str | None,
) -> IssueResult | None:
    """
    POST /repos/{repo}/issues
    title: "[agent-x] structural: {category} in {affected_file}"
    body: what was attempted, why it failed, what human must do manually
    labels: ["needs-human-review", "agent-x", "structural"]
    assignees: [original_author] if provided
    Never raises. GitHub App auth.
    """

Wire into phase2/pipeline.py:
- After decision == "accepted":
  → call create_pr(...) → log pr_created + pr_url → store in MemoryEntry
  → if None → log pr_skipped, never blocks pipeline

- After decision == "structural":
  → call open_structural_issue(...) → log issue_created + url → store in MemoryEntry
  → if None → log issue_skipped, never blocks pipeline

tests/test_pr_creator.py:
- Test GitHub App token generation (mock)
- Test Git Database API flow end-to-end (mock all 11 steps)
- Test draft PR opened with correct audit receipt body
- Test reviewer assigned when original_author provided
- Test structural issue opened with correct labels
- Test graceful failure on 401/403/404 (returns None, no raise)
- Test pipeline: None return never blocks pipeline

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- Real run: accepted fix → Draft PR opened on DevSiddh/-agent-x-test-repo
- PR is in Draft mode, shows "agent-x[bot]" as author, has audit receipt body
- Structural decision → GitHub issue opened with needs-human-review label
- docs/progress.md updated: Step D1 DONE
```
