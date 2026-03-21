# Agent-X v2.2 | Steps D0+ (PENDING — after C2)
# Context Tools for Agent-Y/X

---

## STEP D0 — v2.2 Tools: File Tree Reader + Web Reader + GitHub Search + PDF Summarizer
# Prerequisite: v2.1.5 DONE (C0-C2). Build these after memory engine is stable.
# These are context tools for Agent-Y — plug into ContextBuilder, nothing else changes.

```
You are building Agent-X/Y v2.2 context tools.
Read CLAUDE.md, docs/progress.md before touching anything.
Steps C0-C2 must be DONE. Do not break existing tests.

All tools: phase2/tools/ — one file per tool, one test file per tool.
All tools: 200KB cap, structlog, lazy imports, type hints, __main__ smoke test.
All tools plug into ContextBuilder only — no other file changes.

BUILD IN THIS ORDER:

1. phase2/tools/tree_reader.py
   - read_tree(repo: Path, depth: int = 3) -> dict
     os.walk or pathlib, files + dirs only, NO file contents
     Returns nested dict of project structure
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

4. phase2/tools/pdf_extractor.py  ← NotebookLM-style summarizer
   - summarize_docs(path: Path) -> str
     pdfplumber extracts raw text (cap at 200KB)
     LLM call (deepseek-chat) summarizes into structured output:
       what_it_does, key_endpoints, authentication, rate_limits, key_params
     Returns clean structured summary — NEVER raw PDF dump
   - Only trigger when task contains "API" OR "SDK" OR user uploads PDF
   - Agent-Y ONLY
   - Real example: User uploads Binance API PDF → Agent-Y gets structured
     summary → plans crypto bot with correct endpoints + auth from day 1

tests/test_tools.py — one test file covers all 4:
- Test read_tree returns correct structure at depth limit
- Test fetch_docs strips noise, respects token limit
- Test github_search filters by stars + language
- Test summarize_docs returns structured dict, never raw dump
- Test each tool handles failure gracefully (never raises)

DONE WHEN:
- pytest tests/ → all pass (zero regressions)
- ContextBuilder uses tree + web + RAG for Agent-Y
- ContextBuilder uses github_search + RAG for Agent-X
- pdf summarizer produces structured output on a real PDF
- docs/progress.md updated: Step D0 DONE — tools complete
```
