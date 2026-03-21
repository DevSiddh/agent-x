# Agent-X v1.1–v1.4 | Steps 9–14 (DONE — archived)
# All steps here are COMPLETE. Load only for reference.

---

## STEP 9 — v1.1: Context Builder + RAG Retrieval

```
You are building Agent-X v1.1 — Context Builder upgrade.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.
v1 is COMPLETE. 165 tests pass. Do not break existing tests.

BUILD THIS STEP:

1. phase2/context_builder.py
   - build_context(classifier_result: ClassifierResult, fixture_path: Path) -> str
   - Reads affected file content from fixture (already done in pipeline._build_context — promote to module)
   - Calls get_similar(bug_signature, limit=3) from memory store
   - Formats: file content + 3 past similar fixes (patch + decision) + error summary
   - Returns single context string passed to DeepSeekWorker
   - structlog logging, type hints, Pydantic-safe, __main__ smoke test

2. Update phase2/pipeline.py
   - Replace inline _build_context() + get_similar() call with context_builder.build_context()
   - No other pipeline changes

3. tests/test_context_builder.py
   - Test context includes file content
   - Test context includes similar past fixes when memory has them
   - Test context works when memory is empty
   - Test context works when affected file missing

DONE WHEN:
- pytest tests/ → all pass (165+ tests)
- context_builder.build_context() returns richer context than v1
- docs/progress.md updated: STEP 9 DONE — v1.1
```

---

## STEP 10 — v1.2: Patch Quality Fix (syn_002 / syn_004 / syn_005)

```
You are fixing Agent-X v1.2 — DeepSeek patch quality.
Read CLAUDE.md, docs/progress.md, docs/problems_and_solutions.md before touching anything.
v1.1 must be DONE. 180 tests pass. Do not break existing tests.

CONTEXT:
3 of 5 synthetic cases are still rejected every run:
  syn_002 EnvironmentError → DeepSeek omits +++ header line
  syn_004 RuntimeError     → DeepSeek uses wrong file path in diff header
  syn_005 EnvironmentError → DeepSeek generates corrupt / truncated patch

ROOT CAUSE: prompt does not give enough constraints on diff format.

FIX THIS STEP:

1. phase2/patch_gen/worker.py — harden the system prompt:
   - Add explicit unified diff format example in system prompt
   - System prompt must show: exact --- a/file / +++ b/file format
   - System prompt must forbid: any explanation, markdown, fences, partial diffs
   - Retry prompt (attempt > 1) must include: previous rejection reason + exact format reminder

2. phase1/dataset/synthetic.jsonl — verify expected patches for syn_002/004/005:
   - Confirm each expected_patch field is a valid unified diff
   - Fix any malformed expected patches if found

3. tests/test_patch_gen.py — add regression tests:
   - Test system prompt contains "--- a/" format instruction
   - Test retry prompt contains rejection_reason AND format reminder
   - Test validate_patch rejects diff with missing +++ line
   - Test validate_patch rejects diff with wrong path format

DONE WHEN:
- pytest tests/ → all pass (180+ tests)
- python phase2/pipeline.py → at least 4/5 accepted (up from 2/5)
- docs/progress.md updated: STEP 10 DONE — v1.2
```

---

## STEP 11 — v1.3: Thompson Sampling Strategy Engine
# PREREQUISITE: needs 50+ real pipeline runs in memory.jsonl before this step adds value.
# Unlock condition: check memory/memory.jsonl line count. If < 50, do Step 12 first.

```
You are building Agent-X v1.3 — Thompson Sampling strategy engine.
Read CLAUDE.md, docs/progress.md before touching anything.
Step 10 must be DONE. Check: wc -l memory/memory.jsonl — must be >= 50 lines.
If < 50 lines: STOP. Tell user "Thompson needs more data — run the pipeline on real repos first."

WHY THOMPSON NEEDS DATA:
Thompson Sampling starts at Beta(1,1) = uniform random for all arms.
With < 50 runs it has no signal to exploit — it's identical to random.
With 50+ runs per category it learns which fix strategies win and exploits them.

BUILD THIS STEP:

1. phase2/strategy/__init__.py  (empty)

2. phase2/strategy/thompson.py
   - ThompsonSampler: tracks {bug_signature: (alpha, beta)} — one arm per signature
   - sample(bug_signature: str) -> float
     Draw from Beta(alpha, beta). New arms start at Beta(1, 1).
   - update(bug_signature: str, accepted: bool) -> None
     accepted=True  → alpha += 1
     accepted=False → beta  += 1
   - Persists state to memory/thompson_state.json (lazy path, never module-level)
   - load() / save() called internally — never raises (same pattern as memory store)
   - __main__ smoke test: 10 updates, sample, verify state file written

3. Update phase2/pipeline.py
   - Import ThompsonSampler lazily (inside run())
   - Before DeepSeekWorker: score = sampler.sample(bug_signature) → log as exploration_score
   - After DecisionEngine: sampler.update(bug_signature, accepted=(decision=="accepted"))
   - No other pipeline changes

4. tests/test_thompson.py
   - Test alpha increments on accepted
   - Test beta increments on rejected
   - Test new signature starts at Beta(1,1) → alpha=1, beta=1
   - Test sample() returns float in [0.0, 1.0]
   - Test state persists to JSON and reloads correctly
   - Test save/load never raises on bad path (P8 pattern)
   - Test pipeline integration: exploration_score logged after classify

DONE WHEN:
- pytest tests/ → all pass
- memory/thompson_state.json written after pipeline run
- docs/progress.md updated: STEP 11 DONE — v1.3 Thompson
```

---

## STEP 12 — Claude Code Hooks (safety + auto-format + compaction)
# Source: 50 Claude Code Tips — tips 38, 39, 40, 41

```
You are hardening Agent-X's Claude Code session environment.
Read CLAUDE.md, docs/progress.md before touching anything.
Step 11 must be DONE. 206 tests must still pass after this step.

CONTEXT:
CLAUDE.md is advisory (~80% compliance). Hooks are 100% deterministic.
Three hooks to add to .claude/settings.json (create if absent):

BUILD THIS STEP:

1. .claude/settings.json — add all three hooks:

   Hook A — PreToolUse: block destructive bash commands
   Fires BEFORE Claude runs any Bash command.
   Blocks: rm -rf, drop table, truncate, git reset --hard, git push --force
   If matched: print "BLOCKED: destructive command" and exit 2.

   Hook B — PostToolUse: auto-format Python after every file edit
   Fires AFTER Claude edits or writes any .py file.
   Runs: python -m black "$CLAUDE_FILE_PATH" --quiet 2>/dev/null || true
   (|| true so format failures never block Claude)

   Hook C — Notification: re-inject key context after compaction
   Fires on compaction events.
   Prints reminder: current task + modified files + hard rules summary.
   Keeps Claude from losing the thread in long sessions.

2. Verify hooks work:
   - Try running: !rm -rf /tmp/test_hook → must be blocked
   - Edit any .py file → black must run silently
   - No existing tests should break

3. Copy .claude/settings.json to ~/.claude/settings.json
   so ALL future projects inherit these hooks automatically.

DONE WHEN:
- .claude/settings.json exists with all 3 hooks
- ~/.claude/settings.json updated (global)
- Destructive command is blocked
- Python auto-format runs silently on edit
- pytest tests/ → still 206 passed
- docs/progress.md updated: STEP 12 DONE
```

---

## STEP 13 — File-type Specific Rules (.claude/rules/)
# Source: 50 Claude Code Tips — tip 31

```
You are adding file-type specific rules for Agent-X.
Read CLAUDE.md, docs/progress.md before touching anything.
Step 12 must be DONE.

CONTEXT:
.claude/rules/ files load automatically when Claude works on matching file types.
This means Python rules never load when Claude reads docs. Zero token waste.

BUILD THIS STEP:

1. .claude/rules/python.md — loads for all *.py files
   ---
   paths:
     - "**/*.py"
   ---
   - Type hints on every function — no exceptions
   - structlog only — never import logging
   - Pydantic v2 models for all data structures
   - Env vars lazy inside functions — os.environ.get() never at module level
   - pathlib.Path everywhere — no string path concatenation
   - Specific exceptions only — never bare except:
   - Every module has if __name__ == "__main__": smoke test
   - pytest after every file written

2. .claude/rules/tests.md — loads for tests/*.py
   ---
   paths:
     - "tests/**/*.py"
   ---
   - Every test class covers: happy path + at least one failure path
   - No mocking of core logic — mock only external calls (API, subprocess)
   - Test function names must describe the behavior being tested
   - Use tmp_path fixture for any file I/O
   - Never hardcode paths — use fixture_path from conftest or tmp_path

3. .claude/rules/docs.md — loads for *.md files
   ---
   paths:
     - "**/*.md"
   ---
   - context.md: 80 lines max — index only, never add content directly
   - progress.md: PENDING or DONE only — no diary entries
   - CLAUDE.md: only add a rule if it would prevent a real mistake

DONE WHEN:
- All 3 rule files exist in .claude/rules/
- paths frontmatter correctly set in each
- pytest tests/ → still 206 passed (rules are read-only, no code changes)
- docs/progress.md updated: STEP 13 DONE
```

---

## STEP 14 — CLAUDE.md Litmus Audit + @imports
# Source: 50 Claude Code Tips — tips 29, 32

```
You are auditing and slimming CLAUDE.md using the litmus test + @imports.
Read CLAUDE.md, docs/progress.md before touching anything.
Step 13 must be DONE.

CONTEXT:
Every unnecessary line in CLAUDE.md dilutes the lines that matter.
There is roughly a 150-200 instruction budget before compliance drops.
@imports let Claude read detail on demand without loading it every session.

BUILD THIS STEP:

1. Litmus test — audit every line in CLAUDE.md:
   For each line ask: "Would Claude make a mistake without this?"
   - YES → keep it
   - NO  → delete it
   - Already enforced by a hook or test → delete it (hook owns it now)
   - Duplicated in .claude/rules/python.md → delete it from CLAUDE.md

2. Replace embedded content with @imports where possible:
   Instead of embedding problem descriptions, write:
   See @docs/problems_and_solutions.md for known bugs and fixes.
   Instead of embedding pipeline details in CLAUDE.md, write:
   Pipeline order → @context.md
   Session prompts → @docs/session_prompts.md

3. Add the self-update habit rule (tip 30):
   ## SELF-UPDATE RULE
   When Claude makes a mistake: say "update CLAUDE.md so this doesn't happen again"
   Claude writes its own rule. It loads next session automatically.

4. Add the hooks-vs-suggestions rule (tip 38):
   ## ENFORCEMENT RULE
   CLAUDE.md = suggestions (80% compliance)
   Hooks (.claude/settings.json) = requirements (100% compliance)
   If a rule must ALWAYS be followed → make it a hook, not a line here.

DONE WHEN:
- CLAUDE.md is shorter than before (lines deleted, not added)
- @imports reference heavy docs instead of embedding
- SELF-UPDATE RULE and ENFORCEMENT RULE added
- pytest tests/ → still 206 passed
- docs/progress.md updated: STEP 14 DONE

COPY TO GLOBAL:
After passing: copy updated CLAUDE.md patterns to ~/.claude/CLAUDE.md
so all future projects start with the litmus-tested habits.
```

---

## STEP A4 — Agent-Y v1.1: Prompt Loader (Local Model Ready)
# Trigger: real prod code with sensitive data, OR Ollama trigger fires
# Until trigger fires: DO NOT BUILD. DeepSeek costs <$1/month.

```
You are building Agent-Y v1.1 — local model support for the Reasoner.
Read CLAUDE.md, docs/progress.md, agent_y/CLAUDE.md before touching anything.
Step A3 gate must be DONE. Ollama must be installed locally or on VPS.

WHY THIS EXISTS:
When real repos with proprietary code enter the pipeline, error logs contain
sensitive data (API keys, DB schemas, internal logic). That data must not leave
the machine. This step makes Agent-Y work entirely offline.

BUILD THIS STEP:

1. agent_y/prompt_loader.py
   - load_system_prompt() -> str
     Reads these files in order and concatenates into one system prompt string:
       ~/.claude/CLAUDE.md          → global thinking style + constraints
       agent_y/CLAUDE.md            → Agent-Y specific hard rules
       .claude/rules/python.md      → Python standards (if touching .py)
     Strips frontmatter (--- blocks) before concatenating.
     Falls back gracefully if any file missing (logs warning, skips that file).
     Returns final system prompt string.
   - structlog, type hints, pathlib, __main__ smoke test

2. agent_y/reasoner.py — add local model support
   - Add MODEL env var: REASONER_MODEL (default: "deepseek-reasoner")
   - If REASONER_MODEL starts with "ollama/":
       Use ollama Python client instead of OpenAI
       base_url = "http://localhost:11434/v1"  (Ollama OpenAI-compatible endpoint)
       model = REASONER_MODEL.replace("ollama/", "")  e.g. "qwen2.5:7b"
       system_prompt = load_system_prompt()  ← from prompt_loader.py
   - If REASONER_MODEL == "deepseek-reasoner":
       Current path unchanged (DeepSeek API)
   - No other changes to reason() logic

3. tests/test_prompt_loader.py
   - Test load_system_prompt() returns non-empty string
   - Test missing file is skipped gracefully (no crash)
   - Test frontmatter stripped (--- blocks removed)
   - Test output contains key phrases from CLAUDE.md

SWITCH TO LOCAL:
   Set in .env:
   REASONER_MODEL=ollama/qwen2.5:7b

   Run: ollama pull qwen2.5:7b
   Then: python phase2/pipeline.py
   Reasoner now runs fully offline.

DONE WHEN:
- pytest tests/test_prompt_loader.py → all pass
- REASONER_MODEL=ollama/qwen2.5:7b → pipeline runs, reasoner.ok logged locally
- REASONER_MODEL=deepseek-reasoner → pipeline still works (no regression)
- docs/progress.md updated: Step A4 DONE — Agent-Y v1.1

AFTER THIS STEP:
Follow docs/ollama_migration.md for full migration walkthrough (install, pull, verify, rollback).
```
