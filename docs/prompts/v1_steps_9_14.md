# Agent-X v1.1–v1.4 | Steps 9–14 (DONE — archived)
# All steps here are COMPLETE. Load only for reference.
# Compressed 2026-03-25 — full prompts deleted, summaries only.

---

## STEP 9 — v1.1: Context Builder + RAG Retrieval
**Built:** phase2/context_builder.py — build_context() reads affected file + calls get_similar(limit=3) → formats into prompt context. Pipeline updated to use it.
**Done condition:** 165+ tests pass. build_context() returns richer context than v1.
**Key decisions:** 3-section prompt: file content + past similar fixes + error summary. Promoted from inline _build_context() to standalone module.
**Status: DONE**

---

## STEP 10 — v1.2: Patch Quality Fix
**Built:** Hardened SYSTEM_PROMPT in worker.py (explicit --- a/ +++ b/ format example). Added +++ check and path check to sanitiser.py. Added --ignore-whitespace --recount to runner.py.
**Done condition:** 180+ tests pass. Pipeline result: 5/5 accepted (up from 2/5).
**Key decisions:** Retry prompt always includes rejection_reason + format reminder. sanitiser rejects missing +++ header (syn_002 fix) and wrong file path (syn_004 fix).
**Status: DONE**

---

## STEP 11 — v1.3: Thompson Sampling
**Built:** phase2/strategy/thompson.py — ThompsonSampler, Beta(alpha,beta), sample()/update(), persists to memory/thompson_state.json. Wired into pipeline: sample() before DeepSeekWorker, update() after DecisionEngine.
**Done condition:** 206 tests pass. thompson_state.json written after pipeline run.
**Gate:** memory.jsonl must have >= 50 lines before this adds value. (Met before build.)
**Key decisions:** New arms start at Beta(1,1). save/load never raises. State file = memory/thompson_state.json.
**Status: DONE**

---

## STEP 12 — Claude Code Hooks
**Built:** .claude/settings.json with 3 hooks — PreToolUse (blocks rm -rf, drop table, reset --hard, push --force), PostToolUse (black --quiet on every .py edit), Notification (re-injects context after compaction). Copied to ~/.claude/settings.json.
**Done condition:** Destructive commands blocked. black auto-runs silently. 206 tests still pass.
**Key decisions:** Hooks = 100% enforced. CLAUDE.md = ~80% suggestions. Hooks own enforcement.
**Status: DONE**

---

## STEP 13 — File-type Rules (.claude/rules/)
**Built:** .claude/rules/python.md (loads for **/*.py), .claude/rules/tests.md (loads for tests/**/*.py), .claude/rules/docs.md (loads for **/*.md). Each with paths frontmatter.
**Done condition:** All 3 rule files exist with correct frontmatter. 206 tests still pass.
**Key decisions:** Rules load on demand only — zero token cost when not touching that file type.
**Status: DONE**

---

## STEP 14 — CLAUDE.md Litmus Audit + @imports
**Built:** CLAUDE.md trimmed 153 → 73 lines (deleted: coding standards moved to rules/, stale history, duplicate sections). @imports added for progress.md, session_prompts.md, problems_and_solutions.md. SELF-UPDATE RULE + ENFORCEMENT RULE added.
**Done condition:** CLAUDE.md shorter. @imports reference heavy docs. 206 tests still pass.
**Key decisions:** Litmus test per line: "Would Claude make a mistake without this?" — no → delete.
**Status: DONE**

---

## STEP A4 — Agent-Y v1.1: Local Model (Prompt Loader)
**Trigger:** Real prod repos with sensitive code, OR monthly DeepSeek bill > $30/month.
**Built (when triggered):** agent_y/prompt_loader.py — load_system_prompt() concatenates CLAUDE.md + agent_y/CLAUDE.md + rules/python.md. agent_y/reasoner.py updated for REASONER_MODEL env var (deepseek-reasoner vs ollama/<model>).
**Done condition:** REASONER_MODEL=ollama/qwen2.5:7b → pipeline runs fully offline. REASONER_MODEL=deepseek-reasoner → no regression.
**Key decisions:** Ollama uses OpenAI-compatible endpoint (http://localhost:11434/v1). DeepSeek path unchanged.
**Status: TRIGGER-BASED — do not build until trigger fires**
