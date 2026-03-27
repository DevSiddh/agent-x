# Agent-X + Agent-Y | Architecture Decisions
# Written: 2026-03-22 — CH Y SAI SIDDHARDHA
# Purpose: locked decisions — what we chose and why. Not roadmap. Not status.
# Rule: never duplicate vision.md or progress.md — reference them instead.

---

## D1 — Interface Layer (locked 2026-03-22)

**Decision:** API-first engine with multiple thin interface layers.

**What we chose:**
```
Control API (FastAPI)     ← foundation — everything plugs into this
CLI                       ← agentx fix --log app.log --repo ./my-project
Local log watcher         ← offline trigger, no webhook, watchdog on app.log
Web UI                    ← Streamlit or plain HTML — demo + non-dev users
Telegram bot              ← notifications + mobile approval
Editor plugins            ← after API is stable (see D2)
```

**Why:** GitHub integration is the killer feature (v2.1 DONE). API is the real asset.
Editor plugins, bots, CLI are multipliers — not the core.
Build order: API → CLI → plugins. Never the other way.

**Build at:** v3.2 — full interface layer spec in @docs/vision.md

---

## D2 — Editor Plugin Design (locked 2026-03-22)

**Decision:** Editor-agnostic thin shell. Not VS Code-only.

**Supported editors (same pattern, different language):**
```
VS Code / Cursor   → TypeScript extension API
JetBrains          → Kotlin/Java plugin
Neovim             → Lua plugin
```

**v1 plugin = 3 files only:**
```
extension.ts   — command registration, input capture
api.ts         — POST /fix-local, GET /status/{task_id}
diff.ts        — native diff viewer + Apply button
```

**UX (locked):**
```
1. Select error text → right-click / command palette → "Fix with Agent-X"
2. Plugin sends: error + file content + repo path → POST /fix-local
3. Backend returns: patch + confidence
4. Plugin shows diff preview → user clicks Apply
```

**Hard rules:**
- Zero logic in plugin — all reasoning stays in backend
- No chat, no prompt typing, no conversations in v1
- User always approves before apply — never auto-apply

**API contract (define at v3.2 before any plugin is built):**
```json
POST /fix-local
{ "log": "...", "repo_path": "./my-project", "file": "app.py" }
→ { "patch": "...", "confidence": 0.99, "task_id": "abc123" }
```

---

## D3 — Per-User Memory Isolation (locked 2026-03-22)

**Decision:** Isolated memory per user. No cross-user pollution.

**Problem:** Shared memory.jsonl means User A's Django mistakes corrupt User B's Flask suggestions.

**Solution — 3 tiers:**
```
Tier 1 — User memory     memory/{user_id}/memory.jsonl   ← most specific, highest priority
Tier 2 — Org memory      memory/{org_id}/memory.jsonl    ← team's shared repos
Tier 3 — Global memory   memory/shared/memory.jsonl      ← universal patterns, 100+ confirmed
```

RAG hits: user first → org → global. Most specific wins.

**bug_signature with user scope:**
```python
bug_signature = f"{user_id}:{repo}:{error_type}:{keyword}:{file}"
# e.g. "usr_abc:acme/app:DependencyError:pkg_resources:requirements.txt"
```

**When to implement:** `user_id` goes into every `/fix-local` API call at v3.2.
Retro-fitting later is painful — define it in the API contract from day one.

**Related:** P12 in @docs/problems_and_solutions.md (cross-project pollution — same root cause)

---

## D4 — Long-Term Memory Strategy: Federated Learning (locked 2026-03-22)

**Decision:** Federated Learning as v4+ memory architecture.

**Why not shared training data:**
- User data never leaves their machine
- System gets smarter from all users without privacy risk
- Most defensible technical moat — hard to copy

**How it works:**
```
Each user trains locally on their memory.jsonl
Only model weight UPDATES shared — not raw memory entries
Central model improves from all users
Individual memory stays private
```

**Progression:**
```
Now (v1-v3)    → isolated memory per user_id         ← simple, works
v4             → Contextual Thompson Sampling         ← natural extension of current bandits
v4+            → Federated Learning                  ← real moat
```

**Research keywords (when ready to build):**
- `FedAvg` — core federated averaging algorithm
- `differential privacy` — noise injection for stronger privacy
- `contextual multi-armed bandit` — bridge between now and federated
- `LinUCB` — contextual bandit with user context as input

**Gate:** Do not build until 500+ accepted runs across multiple real users.
Insufficient data = federated learning trains on noise.

---

## D5 — Executor Interface Abstraction (locked — from vision.md)

**Decision:** Abstract executor before adding Docker/VPS backends.

```python
class BaseExecutor:
    def apply_patch(self, repo_path: Path, patch: str) -> Result: ...
    def run_tests(self, repo_path: Path) -> Result: ...

# Implementations:
LocalExecutor   → subprocess git apply (EXISTS NOW)
DockerExecutor  → Docker SDK exec into container (v3.3)
VPSExecutor     → paramiko SSH (v3.3)
```

**Why:** If not abstracted first → pipeline rewrite required when adding Docker.
**Build at:** v3.1 — before any Docker/VPS work begins.

---

## D6 — Agent-Y is Stateless (locked — from vision.md)

**Decision:** Agent-Y reads shared state only. No hidden memory. No side effects.

**Why:** Hidden state = drift. Stateless planner = reproducible reasoning.
Every decision is traceable from shared state alone.

**Enforcement:** Agent-Y output schema is locked — see @docs/vision.md → Protocol section.

---

## D7 — Full Audit Priority Order (locked 2026-03-22)

Cross-reference of BLUNDERS.md + problems_and_solutions.md + risks_and_flaws.md.
Run this audit at every phase boundary.

**Fix now — no gate needed:**
```
I1/P21  ngrok static domain             — 5 min, do before next webhook session
B15     check context.md under 80 lines — 2 min
P26     edge case test audit            — 1 session, before D0
```

**Build next — gates unlocked:**
```
D0  file tree reader + log interpreter  — solves L4/P23
    + Negative Test Check in regression.py — solves R1/L2 (silent killer)
D1  auto-PR with R2 safety design       — gate 101+ ✅ unlocked, solves P20
L6  post-merge awareness                — one webhook handler, after D1
```

**Data-gated — do not touch:**
```
L3/P24  BuildError classifier           — gate: 5+ BuildError runs (have 3)
L5      per-category thresholds         — gate: 50+ runs per category
I3      Thompson cold start seeding     — gate: 3+ new categories emerge
P25     RAG limit 5→7                   — gate: 200+ accepted (have 101+)
```

**Architecture-gated — v3.0+:**
```
L1/P22  multi-file bugs                 — needs Orchestrator
L2/R1   semantic correctness            — needs Agent-Y self-review
```

**Monitor — nothing to do:**
```
R4/S1   memory growth                   — gate: 1,000 entries (have 340)
S3      git bloat → SQLite              — gate: 5,000 commits (have ~30)
R3      DeepSeek SPOF                   — gate: bill >$30 or 2 outages
```

---

## D14 — Test Runner Detection: Bottom-Up Manifest Resolution (locked 2026-03-22)

**Decision:** Extension-based detection replaced by proximity traversal + manifest parsing.

**Why extension fails enterprise:**
- `.ts` = Angular frontend OR NestJS backend OR AWS CDK — same extension, 3 different runners
- Mixed monorepo: React + Django in same repo, `.py` exists in both halves
- Custom build systems: `.java` doesn't always mean `mvn test`

**Algorithm: walk UP from affected_file, not DOWN from repo root:**
```python
def detect_runner(fixture_path: str, affected_file: str) -> tuple[list[str], Path]:
    """
    Returns (command, execution_root). Raises TestRunnerDetectionError if not found.
    execution_root = directory where manifest lives — use as subprocess cwd.
    """
    repo_root = Path(fixture_path).resolve()
    current = (repo_root / affected_file).resolve().parent

    while current >= repo_root:
        # Node.js — check scripts.test, respect lockfile for package manager
        pkg = current / "package.json"
        if pkg.exists():
            data = json.loads(pkg.read_text())
            script = data.get("scripts", {}).get("test", "")
            if script and "no test specified" not in script:
                cmd = ["yarn", "test"] if (current/"yarn.lock").exists() else ["npm","run","test"]
                return cmd, current

        # Python — pyproject.toml or pytest.ini or tox.ini
        if (current/"pyproject.toml").exists() or (current/"pytest.ini").exists():
            return ["python", "-m", "pytest"], current
        if (current/"tox.ini").exists():
            return ["tox"], current

        # Java — Maven or Gradle
        if (current/"pom.xml").exists():
            return ["mvn", "test"], current
        if (current/"build.gradle").exists() or (current/"build.gradle.kts").exists():
            return ["gradle", "test"], current

        # Make
        mf = current / "Makefile"
        if mf.exists() and "test:" in mf.read_text():
            return ["make", "test"], current

        current = current.parent

    raise TestRunnerDetectionError(f"No manifest found for {affected_file}")
```

**Kill switch (never silent fallback):**
```python
class TestRunnerDetectionError(Exception): pass
# pipeline catches → decision = "abstained", reason = "no test runner detected"
# explicit failure builds trust — silent wrong runner destroys it
```

**Signature change in runner.py (breaking):**
```
OLD: get_runner(affected_file: str) -> list[str]          cwd=fixture_path
NEW: detect_runner(fixture_path, affected_file) -> (list[str], Path)  cwd=execution_root
```
subprocess cwd must use execution_root, not fixture_path.
Test runner finds tests natively from execution_root — no manual test discovery needed.

**Speed:** <10ms — pure pathlib + stdlib json/string parsing. No subprocess calls.

**Build at:** C3b — replaces current extension-based get_runner()

---

## D13 — Rate Limiting + Concurrency Architecture (locked 2026-03-22)

**Decision:** Python stdlib + SQLite only. No Redis, no external queue.

**Bottleneck reality check:**
```
GitHub API (5000/hr)  → NOT a bottleneck — limit is PER INSTALLATION not global
                         454 CI failures/hour = entire eng team is on fire
                         Verdict: ignore

DeepSeek API          → REAL bottleneck — concurrent webhook spikes hit 429
SQLite                → NOT a bottleneck — WAL mode handles 1000s of users
memory.jsonl          → REAL bug — concurrent appends corrupt JSON bytes
Installation token    → REAL race condition — concurrent refresh = API thrashing
```

**Fix 1 — DeepSeek 429: exponential backoff with jitter**
```python
# in phase2/patch_gen/worker.py — wrap API call
for attempt in range(MAX_RETRIES):
    try:
        return call_deepseek(prompt)
    except RateLimitError:
        wait = min(2 ** attempt + random.uniform(0, 1), 60)
        log.warning("deepseek.rate_limited", wait=wait, attempt=attempt)
        time.sleep(wait)
```
Jitter prevents thundering herd — concurrent workers don't retry at same second.
**Build at:** Step AUDIT (small addition to worker.py retry loop)

**Fix 2 — Installation token race: SQLite EXCLUSIVE lock**
```python
# github_tokens table: installation_id, token, expires_at
# Before every GitHub API call:
with sqlite3.connect(DB_PATH) as conn:
    conn.execute("BEGIN EXCLUSIVE")           # only one worker refreshes
    row = conn.execute("SELECT token, expires_at FROM github_tokens
                        WHERE installation_id=?", (id,)).fetchone()
    if not row or expires_at < now + 300:     # refresh if <5 min remaining
        token = fetch_new_installation_token(id)
        conn.execute("INSERT OR REPLACE INTO github_tokens VALUES (?,?,?)",
                     (id, token, now + 3600))
    return token
```
**Build at:** D1 (when GitHub App auth is built)

**Fix 3 — memory.jsonl concurrent corruption: SQLite buffer**
```
Problem: concurrent processes appending to .jsonl = interleaved bytes = corrupt JSON
Current: single poll loop = safe for now. Breaks when multiple workers run.

Solution:
  Workers INSERT into SQLite memory_buffer table (SQLite handles locking)
  runner.py cleanup task every 60s:
    SELECT all rows from memory_buffer → append to memory.jsonl (single thread)
    DELETE flushed rows from memory_buffer

memory_buffer table: run_id, repo, decision, patch, timestamp, ...all MemoryEntry fields
```
**Build at:** S3 gate — when running multiple concurrent workers (not urgent yet)
**Note:** Current single-worker poll loop is safe. Buffer needed at platform scale.

**SQLite WAL mode (enable once, protects all tables):**
```python
conn.execute("PRAGMA journal_mode=WAL")   # run on first connection
```
Enables concurrent reads + serialized writes. Handles thousands of users.

---

## D12 — Security Validation Stack (locked 2026-03-22)

**Decision:** Scan the patch, not the repository. Two tools only. Sequential, fail-fast.

**Risk triage (now vs later):**
```
SECRET HARDCODING  → CRITICAL NOW   — LLMs hallucinate dummy keys to pass auth tests
DEPENDENCY CVE     → CRITICAL NOW   — Gateway auto-appends to requirements.txt
OWASP logic flaws  → defer          — no 5s CLI tool catches business logic reliably
LICENSE compliance → defer          — too slow, platform scale only
```

**The Minimum Viable Security Stack (<5s total overhead):**
```
Step 1 — Scope check      (0.1s)  patch >15 lines/file or >50 total → structural
Step 2 — Secret scan      (0.5s)  detect-secrets scan {temp_patch.diff}
                                   scan the DIFF not the repo — 100x faster
                                   reject if high-entropy string detected
Step 3 — SAST             (1.0s)  bandit + radon on patched files (already in C1)
Step 4 — CVE check        (2.0s)  pip-audit -r requirements.txt
                                   ONLY if requirements.txt was modified
                                   skip entirely otherwise — saves 2s per run
Step 5 — Test suite       (~Xs)   Shadow Workspace pytest (Negative Test Check)
```

**Tool choices (locked):**
- `detect-secrets` (Yelp, pip install) — not trufflehog, not git-secrets
- `pip-audit` (PyPA, pip install) — NOT safety (restricted free tier in 2024)

**Rejection messages (must include reason for retry loop):**
```
Secret:  "Security Exception: Potential hardcoded secret in patch. Remove and retry."
CVE:     "Dependency Vulnerability: {package} introduces {CVE-ID}. Use version >{safe_ver}."
```

**Build at:** D0 — security_gate.py alongside Negative Test Check in regression.py

---

## D11 — Atomic Change Set + Shadow Workspace (locked 2026-03-22)

**Decision:** Multi-file tasks are valid. Unit = Atomic Change Set. Apply all or nothing.

**Two caps separated (not conflated):**
```
Patch cap  = 15 lines per file   ← LLM quality gate (DeepSeek degrades over 15 lines)
Task cap   = 1-5 files, 50 total ← testability/reversibility gate
These are different gates. Never mix them.
```

**Why 5 files max:**
Standard atomic change pattern: Interface + Implementation A + Implementation B + Mock + Test.
6+ files = feature refactor, not bug fix → structural escalation is correct.

**Why 50 lines total:**
LLMs degrade after ~15-20 lines continuous generation. 50 total = surgical strikes across files,
not class rewrites. Keeps zero-regression guarantee intact.

**Shadow Workspace (strict git atomicity — solves partial pass risk):**
```
Step 1 — Baseline: run targeted test → MUST FAIL (negative check)
          if passes → test is weak → escalate, do not patch

Step 2 — Shadow commit: apply ALL patches to disk simultaneously
          NEVER test between patches — partial state = Frankenstein codebase

Step 3 — Verify: run targeted test → must pass

Step 4 — Lint gate: python -m mypy on ALL changed files
          catches syntax errors in files not covered by targeted test

Step 5 — Outcome:
          Test + Lint pass → accepted, keep changes
          Test OR Lint fail → git reset --hard HEAD → wipes A+B+C atomically → rejected
```

**For platform (Git Database API via D9):**
Never push partial change sets. Build all blobs + trees in memory first.
Only create branch + PR if ALL patches apply cleanly. No partial commits ever.

**Agent-Y Task schema update (v3.0):**
```json
{
  "task_id": "T2",
  "description": "Fix missing interface implementation",
  "files_to_change": ["auth.py", "auth_impl.py", "test_auth.py"],  // max 5
  "patch_order": ["auth.py", "auth_impl.py", "test_auth.py"],       // dependency order
  "max_total_lines": 50,
  "acceptance_criteria": ["test_auth_validates_token passes"]
}
```

**Structural escalation unchanged:**
5+ files → structural → GitHub issue → human
Radon complexity failure → structural
Architecture redesign → structural

**Build at:** v3.0 Orchestrator (executor needs atomic multi-file apply + reset --hard)

---

## D10 — Context Strategy: AST Map + Blast Radius (locked 2026-03-22)

**Decision:** Replace depth=3 tree with AST signature map + dependency blast radius.

**Why depth=3 fails enterprise:**
- 50k file monorepo at depth=3 → 150,000+ tokens → context window blown before error is read
- File paths tell Agent-Y nothing about what code does
- "Lost in the Middle" — LLM forgets the actual error when buried in noise

**Two-layer context (total budget ~4,000-5,000 tokens):**

```
Layer 1 — AST Repo Map (~2,000 tokens)
  ast_mapper.py extracts signatures only (no bodies):
    class names + method signatures
    top-level function signatures
    one-line module docstring
  Hard cap: stops at 2,000 tokens, closest files first
  Agent-Y sees full architecture skeleton cheaply

Layer 2 — Blast Radius (~2,000 tokens)
  blast_radius.py parses imports of affected_file:
    Tier 1: affected_file (always, full content)
    Tier 2: files imported BY affected_file
    Tier 3: files that import affected_file (upstream consumers)
  Max 8 files total, sorted by import depth
  Agent-Y sees only the 4-8 files that actually matter
```

**Layer 3 — Interactive Retrieval (v3.0, not now):**
Agent-Y calls `read_file(path)` / `search_codebase(keyword)` tools when it needs more.
Requires Orchestrator tool-calling loop — build at v3.0.

**Token budget comparison:**
```
depth=3 tree on monorepo  → 150,000+ tokens  → fails
RAG-filtered tree          → 20,000 tokens   → misses dependencies
AST Map + Blast Radius     → ~5,000 tokens   → enterprise standard
```

**Build at:** D0 — ast_mapper.py + blast_radius.py replace tree_reader.py

---

## D9 — GitHub Integration: App not PAT, Draft PR, Git Database API (locked 2026-03-22)

**Decision:** GitHub App + Git Database API + Draft PR always. Never PAT, never auto-merge.

**Why PAT fails enterprise:**
- PAT commits show as your personal account — SOC2 violation (human impersonation)
- PAT has no scope isolation — enterprise admins can't audit blast radius
- PAT can't auto-sign commits — fails branch protection "require signed commits" rule

**Four pillars (all required together):**

```
1. Identity    → GitHub App (APP_ID + PRIVATE_KEY + INSTALLATION_ID)
               commits show as "agent-x[bot]" — zero ambiguity, full audit trail

2. Commit API  → Git Database API (POST /git/commits) not PUT /contents
               auto-signs every commit → passes "Verified Signature" protection rules
               no local git clone needed → works in serverless/container environments

3. Branch      → namespace: agent-x-fixes/{bug_signature_hash}
               strictly isolated from main/develop/release branches

4. PR mode     → always draft: true
               CI runs against bot's code before humans see it
               original commit author auto-assigned as reviewer
               bot NEVER merges — human must mark ready + click merge
```

**Env vars (all lazy inside functions):**
```
GITHUB_APP_ID
GITHUB_APP_PRIVATE_KEY      ← multiline .pem content
GITHUB_APP_INSTALLATION_ID  ← per-repo, get from GitHub App settings
```

**Build at:** Step D1

---

## D8 — Thompson Arm Design: Category × Ecosystem (locked 2026-03-22)

**Decision:** Arms = `{Category}_{Ecosystem}` — not flat category, not full cross-product.

**Why:**
```
Category only          → ~10 arms  → Python pip failure = Node npm failure → wrong signal
Cat × Lang × Size      → ~500 arms → permanent cold start, never converges
Category × Ecosystem   → ~30 arms  → sweet spot — isolated signal, fast convergence
```

**Excluded dimensions (deliberate):**
- Repo size → already handled by 15-line structural cap
- Framework → too granular, explodes arm count
- File size → structural cap handles it

**Arm examples:**
```
DependencyError_Python, DependencyError_Node, DependencyError_Java
RuntimeError_Python,    RuntimeError_Node,    RuntimeError_Java
ConfigError_Python,     SyntaxError_Java,     EnvironmentError_Node
```

**Migration required at C3b (breaking change):**
All existing arms get `_Python` suffix. Migration script in thompson.py.
```
"DependencyError" → "DependencyError_Python"
"RuntimeError"    → "RuntimeError_Python"
```

**Seeding decay factors (two scenarios):**
```
New language for known category  → 0.25 × known_sibling (harder boundary)
New category in known ecosystem  → 0.50 × similar_category (softer boundary)
Global fallback                  → 0.25 × global_avg × 2
```

**Build at:** C3b — when multi-language support lands. Not before.

---

---

## D15 — Transparent Expert Layer (locked 2026-03-22)

**Decision:** Every accepted fix outputs three things, not one: diagnosis + patch + complexity delta.
Black-box fixes (patch only) kill user trust. Explanation is the USP.

**What we chose:**

**1 — Delta Diagnosis (Agent-Y output, ~50 extra tokens, nearly free)**
```
Add to ReasonerOutput schema:
  diagnosis: str   # max 200 chars, non-empty
  e.g. "ZeroDivisionError in utils.py — missing empty-list guard before division on line 42"

Add to Agent-Y system prompt:
  "diagnosis": "one sentence: what is broken and why, plain English, no jargon"

Wire through: ReasonerOutput → pipeline.py → MemoryEntry → PR body
```

**2 — Complexity Delta (Radon, $0 — already installed)**
```
Before patch: get_complexity(file_path) → complexity_before
After patch:  get_complexity(file_path) → complexity_after
delta = after - before
If delta > +2.0 → log.warning("regression.complexity_increase") — warns, does NOT reject
Include in PR body and dashboard panel

Radon already installed at C1. Zero new dependency.
```

**3 — Ghost Test (existing CI test as proof, $0)**
```
The failing_test_name from CI log = the ghost test
"This test ❌ failed on broken code, ✅ passes with this fix"
Already proven by Negative Test Check (D0)
Surface it explicitly in PR body — no new work, just display
```

**PR body format (Transparent Expert — locked):**
```
**Diagnosis:** {diagnosis}
**Complexity:** {before:.1f} → {after:.1f} ({delta:+.1f})
**Proof:** `{failing_test_name}` — ❌ before, ✅ after
**Diff:** ...
```

**Why NOT generate new Ghost Tests via LLM:**
Generating a minimal reproduction test = extra API call per run.
Using the existing failing CI test = same proof, zero cost.
LLM-generated tests are the wrong direction — they can be wrong.
The existing CI test is ground truth.

**Build at:** D1 — diagnosis added to Agent-Y at same time as PR creator.
Complexity delta added to regression.py at D1 (Radon already there).

---

## Decision Index

| ID | Decision | Locked | Build at |
|----|----------|--------|----------|
| D1 | API-first interface layer | 2026-03-22 | v3.2 |
| D2 | Editor-agnostic plugin design | 2026-03-22 | after v3.2 |
| D3 | Per-user memory isolation | 2026-03-22 | v3.2 API contract |
| D4 | Federated Learning (v4+ memory) | 2026-03-22 | gate: 500+ runs |
| D5 | Executor interface abstraction | 2026-03-20 | v3.1 |
| D6 | Agent-Y stateless design | 2026-03-20 | enforced now |
| D15 | Transparent Expert — diagnosis + complexity delta + ghost test display | 2026-03-22 | D1 |
