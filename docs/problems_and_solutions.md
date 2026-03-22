# Agent-X | Problems & Solutions Master Log
# Last updated: 2026-03-22
# Source: Full audit session — validated against codebase + ChatGPT cross-check

---

## PHASE 0 — CRITICAL BLOCKERS (must fix before anything runs)

---

### P1 — OpenClaw CLI commands don't exist
- **Phase:** 2 / Executor
- **File:** phase2/executor/openclaw_runner.py
- **Problem:** CLAUDE.md specifies `openclaw sandbox execute` and `openclaw sandbox run`.
  These subcommands do not exist. OpenClaw's real sandbox CLI only has:
  explain / list / recreate. It routes exec calls via Docker internally, not via CLI.
- **Solution:** Replace with local subprocess executor.
  ```python
  subprocess.run(["git", "apply", "patch.diff"], cwd=fixture_path, check=True)
  subprocess.run(["pytest", "tests/", "--tb=short", "--json-report",
                  "--json-report-file=report.json"], cwd=fixture_path)
  ```
- **Status:** PENDING — will implement in phase2/executor/

---

### P2 — No fixture repos for git apply
- **Phase:** 2 / Executor
- **File:** fixtures/ (does not exist yet)
- **Problem:** `git apply` requires an actual git repo with the exact files
  referenced in the patch. Synthetic cases patch different files per case.
  One generic repo cannot cover all 5 patches.
- **Solution:** Create 5 fixture repos, one per synthetic case:
  ```
  fixtures/
  ├── syn_001/  requirements.txt with missing setuptools
  ├── syn_002/  Makefile missing --no-build-isolation
  ├── syn_003/  app/database.py missing model import
  ├── syn_004/  app/schemas.py with pydantic namespace conflict
  └── syn_005/  scripts/restart.sh missing pkill + cache clear
  ```
  Each fixture is a real git repo (git init + initial commit) so patches apply cleanly.
- **Status:** PENDING — build before executor tests

---

### P3 — LLM returns markdown fences, not raw unified diff
- **Phase:** 2 / PatchGen
- **File:** phase2/patch_gen/sanitiser.py
- **Problem:** DeepSeek (and all LLMs) wrap output in ```diff fences with explanatory
  text. `git apply` rejects anything that isn't a raw unified diff starting with `---`.
- **Solution:** Two-layer defense.
  Layer 1 — Prompt enforcement (system prompt):
  ```
  Return ONLY a unified diff. No explanation. No markdown.
  No code fences. Start with --- and nothing else before it.
  ```
  Layer 2 — Sanitiser strips fences regardless:
  ```python
  def strip_markdown_fences(text: str) -> str:
      text = re.sub(r"^```[a-z]*\n", "", text, flags=re.MULTILINE)
      text = re.sub(r"^```$", "", text, flags=re.MULTILINE)
      for i, line in enumerate(text.splitlines()):
          if line.startswith("---"):
              return "\n".join(text.splitlines()[i:])
      return text
  ```
- **Status:** PENDING — implement in sanitiser.py

---

### P4 — GITHUB_TOKEN read at module import time
- **Phase:** 1 / LogFetcher
- **File:** phase1/log_fetcher/fetcher.py (line 16)
- **Problem:** `GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")` evaluated once
  at import. Tests using monkeypatch.setenv() set it AFTER import → always empty.
- **Solution:** Lazy function called inside each function that needs it:
  ```python
  def _get_token() -> str:
      token = os.environ.get("GITHUB_TOKEN", "")
      if not token:
          raise EnvironmentError("GITHUB_TOKEN not set")
      return token
  ```
- **Status:** PENDING — fix when fetcher.py is rebuilt

---

## PHASE 1 — SYSTEM CORRECTNESS (fix after blockers)

---

### P5 — Confidence score not calibrated
- **Phase:** 2 / Classifier
- **File:** phase2/classifier/regex_pass.py
- **Problem:** The 0.85 threshold is arbitrary. Without calibration data,
  the safety gate will either block too many valid cases or pass garbage through.
- **Solution:** For v1, just log every confidence score + outcome.
  After 20-30 real runs, adjust threshold based on actual data.
  Do NOT over-engineer now.
- **Status:** LOG ONLY for v1

---

### P6 — Memory has no deduplication
- **Phase:** 2 / MemoryStore
- **File:** phase2/memory/store.py
- **Problem:** Append-only JSONL means same bug_signature can appear 50+ times.
  Future RAG lookups will return stale/duplicate "fixes."
- **Solution:** Check before write:
  ```python
  def already_fixed(bug_signature: str, repo: str) -> bool:
      if not MEMORY_PATH.exists():
          return False
      with open(MEMORY_PATH) as f:
          for line in f:
              e = json.loads(line)
              if e["bug_signature"] == bug_signature and e["repo"] == repo:
                  if e["decision"] == "accepted":
                      return True
      return False
  ```
- **Status:** PENDING — implement in memory store

---

### P7 — Regression check is undefined
- **Phase:** 2 / Executor
- **File:** phase2/executor/regression.py
- **Problem:** "new failures? ROLLBACK" has no implementation spec.
  No concrete comparison mechanism defined.
- **Solution:** Use pytest --json-report before and after patch:
  ```python
  # before_report = run_pytest(fixture_path)  → capture failed test names
  # apply patch
  # after_report  = run_pytest(fixture_path)  → capture failed test names
  # new_failures  = after_failures - before_failures
  # if new_failures > 0 → regression = True → rollback
  ```
  Dependency: add `pytest-json-report` to requirements.txt
- **Status:** PENDING — implement in regression.py

---

### P8 — Unhandled exceptions skip memory write (violates Hard Rule 4)
- **Phase:** 2 / Pipeline
- **File:** phase2/pipeline.py
- **Problem:** If any stage raises, the whole run dies and nothing is written to
  memory.jsonl. Hard Rule 4: ALWAYS append to memory regardless of outcome.
- **Solution:** finally block guarantees write:
  ```python
  outcome = build_default_entry(run_id)
  try:
      outcome = run_all_stages(case)
  except Exception as e:
      outcome["error"] = str(e)
      outcome["decision"] = "abstained"
  finally:
      memory_store.append(outcome)  # ALWAYS runs, no exceptions
  ```
- **Status:** PENDING — bake into pipeline.py from day one

---

## PHASE 2 — STABILITY (fix after core loop works)

---

### P9 — ZIP log file ordering is non-deterministic
- **Phase:** 1 / LogFetcher
- **File:** phase1/log_fetcher/fetcher.py
- **Problem:** `zf.namelist()` order not guaranteed. GitHub step logs are named
  like `1_Setup.txt`, `2_Build.txt`. Wrong order → error window from wrong step.
- **Solution:** Sort filenames before iterating:
  ```python
  for name in sorted(zf.namelist()):
  ```
- **Status:** PENDING — fix when fetcher.py is rebuilt

---

### P10 — DB_PATH is module-level in server.py (test fragility)
- **Phase:** 1 / Webhook
- **File:** phase1/webhook/server.py
- **Problem:** Tests must monkey-patch DB_PATH after import. If lifespan runs
  before patch, real queue.db is created on disk.
- **Solution:** Already partially addressed in current server.py rewrite.
  Tests override _server_mod.DB_PATH before TestClient starts. Acceptable for v1.
- **Status:** MONITORED — acceptable workaround in place

---

### P11 — Retry sends identical prompt (3 retries = 3 identical failures)
- **Phase:** 2 / PatchGen
- **File:** phase2/patch_gen/worker.py
- **Problem:** When sanitiser rejects a patch (too many lines or bad format),
  the retry sends the exact same prompt → same output → same rejection → wasted calls.
- **Solution:** Retry prompt must include failure context:
  ```python
  retry_prompt = f"""
  Your previous patch was REJECTED.
  Reason: {rejection_reason}
  Lines generated: {line_count} (maximum allowed: 15)

  Generate a NEW patch under 15 lines. Use a different, simpler approach.
  Return ONLY the unified diff, nothing else.
  """
  ```
- **Status:** PENDING — implement in worker.py retry loop

---

### P12 — Bug signature has no repo scope (cross-project pollution)
- **Phase:** 2 / All
- **File:** everywhere bug_signature is used
- **Problem:** `"DependencyError:pkg_resources:requirements.txt"` is identical
  for acme/app and other/repo. Memory lookups surface fixes from wrong projects.
- **Solution:** Include repo in signature:
  ```python
  bug_signature = f"{repo}:{failure_category}:{keyword}:{affected_file}"
  # e.g. "acme/app:DependencyError:pkg_resources:requirements.txt"
  ```
- **Status:** PENDING — apply consistently when building Phase 2

---

## PHASE 3 — CLEANUP (do last, after system runs end-to-end)

---

### P13 — Missing Phase 2 dependencies in requirements.txt
- **Files:** requirements.txt
- **Missing:** openai, pydantic>=2.0, pytest-json-report, structlog (already added)
- **Status:** PENDING — add before Phase 2 build starts

### P14 — Mixed logging: stdlib logging in fetcher.py, structlog elsewhere
- **File:** phase1/log_fetcher/fetcher.py
- **Status:** PENDING — fix when fetcher.py is rebuilt

### P15 — No phase2/__init__.py
- **File:** phase2/__init__.py (and all subpackages)
- **Status:** PENDING — create when Phase 2 scaffold is built

### P16 — Windows path separators in subprocess calls
- **File:** phase2/executor/
- **Problem:** Hardcoded paths may fail on Windows if not using pathlib consistently
- **Solution:** Use `Path` objects and pass `cwd=` to subprocess, never string concat paths
- **Status:** PENDING — enforce in executor build

---

### P17 — uvicorn not on PATH on Windows Store Python
- **Phase:** Dev setup / v2.1
- **File:** Makefile / scripts/verify_env.py
- **Problem:** Windows Store Python installs scripts to a user-local path not on PATH.
  Running `uvicorn` directly fails with "not recognized as internal or external command".
  Affects any CLI tool installed via pip (black, uvicorn, pytest, etc.).
- **Solution:** Always invoke via `python -m <tool>`:
  ```bash
  python -m uvicorn phase1.webhook.server:app --port 8000
  python -m pytest tests/
  python -m black .
  ```
  Add to scripts/verify_env.py: check `python -m uvicorn --version` not `uvicorn --version`.
  Add to Makefile: all server/test targets use `python -m` prefix.
- **Status:** NOTED — apply to all future shell commands in this project

---

### P18 — GITHUB_WEBHOOK_SECRET not loaded when uvicorn started without --env-file
- **Phase:** Dev setup / v2.1
- **File:** scripts/verify_env.py + Makefile
- **Problem:** Starting uvicorn without `--env-file .env` means `GITHUB_WEBHOOK_SECRET`
  is never loaded. Server starts fine but returns 401 on every webhook request.
  No error log says "secret missing" — just silent 401s. Very hard to debug.
- **Solution:** Always start server with `--env-file .env`:
  ```bash
  python -m uvicorn phase1.webhook.server:app --port 8000 --env-file .env
  ```
  Add to scripts/verify_env.py: check `GITHUB_WEBHOOK_SECRET` is set before server start.
  Add to Makefile: `serve` target always includes `--env-file .env`.
- **Status:** NOTED — enforce in Makefile serve target

---

### P19 — GitHub Actions YAML 'on' is a reserved word
- **Phase:** Dev setup / v2.1
- **File:** .github/workflows/ci.yml in test repos
- **Problem:** In YAML 1.1 (used by GitHub Actions), `on` is a boolean reserved word.
  Writing `on: [push]` causes "No event triggers defined in `on`" error.
  Workflow fails immediately at parse time — no useful CI logs generated.
- **Solution:** Write the trigger key unquoted with block style:
  ```yaml
  on:
    push:
      branches:
        - main
  ```
  GitHub Actions parser handles this correctly. Do NOT use `on: [push]` inline style.
  Edit workflow files directly in GitHub web editor to avoid local encoding issues.
- **Status:** NOTED — use block style on: in all future workflow files

---

## PHASE 4 — KNOWN LIMITATIONS WITH SCHEDULED FIXES

---

### P20 — No auto-PR (patch never pushed back to repo)
- **Phase:** v2.2 / Step D1
- **Problem:** Pipeline accepts a patch locally but never pushes it to GitHub.
  The fix exists in memory but the repo stays broken.
- **Gate:** 101+ accepted — ALREADY UNLOCKED
- **Solution:** GitHub API flow:
  ```python
  # 1. Create branch: PATCH-{run_id}
  # 2. Commit changed file(s) via GitHub Contents API
  # 3. Open PR with description, patch diff, and test results
  POST /repos/{owner}/{repo}/git/refs       # create branch
  PUT  /repos/{owner}/{repo}/contents/{path} # commit patch
  POST /repos/{owner}/{repo}/pulls           # open PR
  ```
- **When:** Step D1 — implement after D0 (context tools)
- **Status:** PENDING

---

### P21 — ngrok URL changes on every restart
- **Phase:** v2.1 / Dev setup
- **Problem:** Free ngrok URL changes on restart → GitHub webhook breaks → must reconfigure manually.
- **Solution:** Use ngrok static domain (ngrok free tier allows 1 static domain).
  ```bash
  ngrok http --domain=<your-static-domain>.ngrok-free.app 8000
  ```
  Update GitHub webhook URL once to the static domain — never changes again.
- **When:** Next dev session that needs webhook — do it once, done forever
- **Status:** PENDING

---

### P22 — Single-file patch limit (multi-file bugs always abstain)
- **Phase:** v3.0 / Orchestrator
- **Problem:** Hard Rule 2 caps patches at 15 lines / 1 file. Multi-file bugs
  (e.g. missing import in A, broken interface in B) are correctly escalated but
  never fixed — they just accumulate in memory as "structural".
- **Solution:** Agent-Y plans a sequence of single-file tasks. Orchestrator
  executes them one at a time, each with its own patch + test cycle.
  No single patch grows beyond the 15-line cap.
- **When:** v3.0 Orchestrator (Step C0-C4 of v3.0 roadmap)
- **Status:** LOCKED — needs Orchestrator first

---

### P23 — No codebase architecture understanding
- **Phase:** v2.2 / Step D0
- **Problem:** Agent-Y plans a fix without knowing the project structure.
  Causes wrong file paths, missed dependencies, and incorrect import guesses.
- **Solution:** File tree reader tool — passes full directory layout to Agent-Y before planning.
  ```python
  def read_file_tree(repo_path: Path, max_depth: int = 3) -> str:
      # walks repo_path up to max_depth, returns indented tree string
      # excludes: .git/, __pycache__/, node_modules/, *.pyc
  ```
- **When:** Step D0 — first context tool to build
- **Status:** PENDING

---

### P24 — BuildError always abstains (Docker logs have no Python tracebacks)
- **Phase:** v2.2+ / Hard limit
- **Problem:** Docker build failures log the command that failed (e.g. `RUN pip install`)
  but not the Python traceback. Classifier finds no recognisable pattern → confidence 0.0
  → observer mode. BuildError is currently unfixable.
- **Real fix:** Classify from the Docker command that failed, not the traceback.
  ```
  "RUN pip install -r requirements.txt" + exit code 1
      → DependencyError → same fix pipeline as ModuleNotFoundError
  "RUN python setup.py build" + exit code 1
      → BuildError:setup_failure → new rule class
  ```
- **Gate:** Need 5+ real BuildError runs to map actual log patterns before coding
- **Status:** DATA-GATED — do not build until gate is met

---

### P25 — RAG limit too conservative (3 past fixes, should be 5-7)
- **Phase:** v2.2 / context_builder.py
- **Problem:** RAG returns only 3 past fixes (raised to 5 in C3). With 200+ accepted
  runs, 5 is still under-using available signal. More past fixes = better patch quality,
  especially for rare error patterns.
- **Solution:** After 200+ accepted runs, raise to 7 and monitor context window usage.
  Cap total RAG section at 800 tokens regardless of limit to prevent overflow.
- **Gate:** 200+ accepted runs (currently 101+)
- **Status:** PENDING — monitor, raise when gate met

---

### P26 — Edge case tests missing (happy path only)
- **Phase:** All / tests/
- **Problem:** Most test files only test valid input → valid output. Production sends
  malformed data, missing files, API failures. Nothing crashes in tests. Everything
  crashes in prod. Found during 2026-03-22 blunders audit (B14).
- **Which modules are highest risk:**
  - phase2/patch_gen/worker.py — what if DeepSeek returns empty string?
  - phase2/memory/store.py — what if memory.jsonl is corrupt/truncated?
  - phase3/log_cleaner_real.py — what if log is binary or all whitespace?
  - phase2/gateway.py — what if rules file is missing?
- **Solution:** For every module, add at least one test per failure mode:
  ```python
  # 1. Missing input
  def test_worker_empty_response(): ...
  # 2. Malformed input
  def test_cleaner_binary_log(): ...
  # 3. External call fails
  def test_worker_api_timeout(): ...
  # 4. Write to disk fails
  def test_store_disk_full(tmp_path): ...
  ```
- **When:** Audit tests/ before Step D0 — 1 session, no new modules needed
- **Status:** PENDING
