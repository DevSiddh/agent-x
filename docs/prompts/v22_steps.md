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

0. Fix context_builder.file_missing (P23 blocker — affects every real run)
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

1. phase2/tools/tree_reader.py
   - read_tree(repo: Path, depth: int = 3) -> dict
     os.walk or pathlib, files + dirs only, NO file contents
     Returns nested dict of project structure
     Exclude: .git/, __pycache__/, node_modules/, *.pyc
   - Use: Agent-Y sees full project layout before planning
     Prevents creating files that already exist
   - Inject into ContextBuilder for Agent-Y only

2. phase2/tools/web_reader.py
   - fetch_docs(url: str, max_tokens: int = 2000) -> str
     httpx GET, BeautifulSoup parse
     Strip: nav, footer, ads, scripts, duplicate content
     Return clean text, max 2 pages, max 2000 tokens
   - Use: Agent-Y reads current API docs before planning
     Fixes outdated LLM knowledge for fast-moving APIs
   - Agent-Y ONLY

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
- Test read_tree returns correct structure at depth limit
- Test fetch_docs strips noise, respects token limit
- Test github_search filters by stars + language
- Test summarize_docs returns structured dict, never raw dump
- Test each tool handles failure gracefully (never raises)

DONE WHEN:
- pytest tests/ -> all pass (zero regressions)
- context_builder no longer logs file_missing on real GitHub runs
- ContextBuilder uses tree + web + RAG for Agent-Y
- ContextBuilder uses github_search + RAG for Agent-X
- pdf summarizer produces structured output on a real PDF
- docs/progress.md updated: Step D0 DONE
```

---

## STEP D1 — Auto-PR: push accepted patch back to GitHub
# Prerequisite: D0 DONE. Gate: 101+ accepted runs (ALREADY UNLOCKED as of 2026-03-22).
# Fixes P20 (patch accepted locally but repo stays broken).

```
You are building the auto-PR feature for Agent-X v2.2.
Read CLAUDE.md, docs/progress.md before touching anything.
Step D0 must be DONE. Do not break existing tests.

FILE: phase2/tools/pr_creator.py

class PRResult(BaseModel):
    pr_url: str
    branch: str
    success: bool

def create_pr(
    repo: str,           # "owner/repo"
    patch: str,          # raw unified diff
    affected_file: str,  # relative path in repo
    run_id: str,
    category: str,       # DependencyError etc
    test_summary: str,   # "3 passed, 0 failed"
) -> PRResult | None:
    """
    1. Fetch current file content + SHA from GitHub Contents API
    2. Apply patch locally (patch.apply_patch_to_string())
    3. Create branch: agent-x/fix-{run_id}
    4. Commit patched file via PUT /repos/{repo}/contents/{path}
    5. Open PR via POST /repos/{repo}/pulls
       title: "[agent-x] fix {category} — {affected_file}"
       body: includes diff, test_summary, run_id
    Return PRResult or None on any failure (never raises)
    GITHUB_TOKEN lazy inside function
    """

Wire into phase2/pipeline.py:
- After decision == "accepted" and regression check passes
- Call create_pr(...) — if PRResult.success → log pr_created + pr_url
- If None → log pr_skipped, continue (never blocks pipeline)
- Store pr_url in MemoryEntry (add optional field)

tests/test_pr_creator.py:
- Test full flow with mocked GitHub API (create branch, commit, open PR)
- Test graceful failure on 401/404 (returns None, no raise)
- Test pipeline integration: pr_url logged in memory on accepted fix
- Test pipeline: None return from create_pr does not break pipeline

DONE WHEN:
- pytest tests/ -> all pass (zero regressions)
- Real run: accepted fix -> PR opened on DevSiddh/-agent-x-test-repo
- PR visible on GitHub with correct title, diff, and test summary
- docs/progress.md updated: Step D1 DONE
```
