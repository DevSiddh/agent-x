# Agent-X | Progress Tracker
# Last updated: 2026-03-28
# Full build history (v1–v2.3): docs/archive/progress_v1_v2.md

---

## North Star
Autonomous software engineer. Agent-Y (brain) + Agent-X (hands).
Full vision → @docs/vision.md

---

## Current Status: v4.1 IN PROGRESS — 657 tests passing
memory.jsonl: 605 entries | registry.jsonl: LIVE | skill_vault.jsonl: LIVE
BM25 fully live (rank_bm25). End-to-end proven on simple tasks only.
Next: FIX-1 through FIX-9 — unlock real multi-file projects (FastAPI, bots, CLI tools).

---

## Build History (summary)

| Version | Steps | Status | Tests | Date |
|---------|-------|--------|-------|------|
| v1 Phase 1 + Steps 0–8 | Foundation + pipeline | DONE | 165 | 2026-03-20 |
| v1.1–v1.4 Steps 9–14 | RAG, patch quality, Thompson, hooks, rules | DONE | 206 | 2026-03-20 |
| v2.0 Steps A0–A3 | Agent-Y reasoning layer | DONE | 233 | 2026-03-20 |
| v2.1 Steps B0–B3 | Real GitHub webhook integration | DONE | 304 | 2026-03-21 |
| v2.1.5 Steps C0–C2 | Memory engine + hardening + gateway | DONE | 311 | 2026-03-22 |
| v2.1.6 C3+AUDIT+C3b | Multi-language + 13 audit fixes + embedding classifier | DONE | 363 | 2026-03-22 |
| v2.2 Steps D0–D1 | Context tools + auto-PR | DONE | 480 | 2026-03-24 |
| v2.3 Steps E0–E1 | Dashboard + failure learning | DONE | 491 | 2026-03-24 |

Full step details → @docs/archive/progress_v1_v2.md

---

## Active: v3.0 Creation Mode

| Step | Description | Status |
|------|-------------|--------|
| Step Y-C0 | Agent-Y creation: schemas.py (6 models) + plan_goal() + replan() | DONE — 2026-03-25 |
| Step X-C0 | Agent-X task mode: write_file() + StateManager + Orchestrator loop | DONE — 2026-03-26 |
| Step Y-C1 | Skill Vault + Best-of-N + retrospective.py | DONE — 2026-03-26 |

Prompt → @docs/prompts/v30_creation_steps.md

---

## Pending (data-gated)

| Step | Description | Gate |
|------|-------------|------|
| Step C4 | Playwright visual validation | Blocked — build after v3.0 |
| Step E2 | Cross-repo pattern detection | Gate: 3+ repos |
| Step RAG-NEG | Negative RAG / Autopsy Protocol | Gate: 10+ test_failure rejections |
| Step A4 | Prompt loader + local model | Gate: >$30/mo API bill |

---

## v3.0 Architecture — LOCKED (2026-03-25)

Schemas: SharedState, Task(TaskAction enum), AcceptanceCriteria(min 3 cases), ArtifactEntry, ReplanAnalysis, ReplanResponse
Full spec → @docs/prompts/v30_creation_steps.md
Hard rules → CLAUDE.md → "v3.0 Hard Rules" section

---

## Hooks + Skills Architecture — LOCKED (2026-03-25)

| Decision | Rule |
|----------|------|
| Hook execution | Direct import; subprocess only for security_scan |
| Skill injection | Context into Agent-Y prompt — never writes to plan[] directly |
| Skill loading | Keyword match on goal field against skills/manifest.yaml |
| Hook failure | hard hooks (security/type) → FAIL task; soft hooks (format/notify) → WARN only |
| Adaptive skills | Thompson on skill templates → skill_state.json; gate: 20 runs/skill |

Build order: hooks/skills at v3.2 — after v3.0 Orchestrator exists

---

## Build History (v3–v4.1)

| Version | Steps | Status | Tests | Date |
|---------|-------|--------|-------|------|
| v3.0.1 Y-C0 | schemas + plan_goal() + replan() | DONE | 493 | 2026-03-25 |
| v3.0.2 X-C0 | write_file() + StateManager + Orchestrator | DONE | 517 | 2026-03-25 |
| v3.0.3 Y-C1 | SkillVault + Best-of-N + Retrospective | DONE | 540 | 2026-03-25 |
| v3.1 | .agent/context.md + registry.jsonl | DONE | 559 | 2026-03-25 |
| v3.2 | Brief watcher + Streamlit + Telegram + PR | DONE | 559 | 2026-03-25 |
| session-1 | BUG-1/2/3 fixes | DONE | 559 | 2026-03-26 |
| session-2 | GAP-3 + M1 + M3 + M4 | DONE | 559 | 2026-03-26 |
| session-3 | DeepSeek wired + plan_goal() + is_done fix | DONE | 576 | 2026-03-26 |
| Q1 fix | registry status updates | DONE | 576 | 2026-03-26 |
| bugfix session | rollback staged files + TestReport rename | DONE | 580 | 2026-03-26 |
| Q3 fix | _commit_context() tests + Q3 marked done | DONE | 585 | 2026-03-26 |
| yc0 fix | task.action trusted over is_new_file; test mock for plan_goal | DONE | 604 | 2026-03-26 |
| telegram bot | telegram_bot.py — poll text/files → projects/new/ → run_loop() | DONE | 614 | 2026-03-26 |
| BM25 install | rank_bm25 installed — Jina 800MB ripped out — zero RAM retrieval | DONE | 657 | 2026-03-27 |
| viva prep | Gemini Reviews 3+4+5 logged — BM25F, LoRA quality, Thompson decay locked | DONE | 657 | 2026-03-27 |
| FIX-1 | _run_ast_mapper per-file scope + global_interfaces injection + SkillVault wiring | DONE | 657 | 2026-03-28 |

## Locked Decisions (2026-03-27) — do not relitigate

| Decision | What | Gate |
|----------|------|------|
| BM25 precision stack | L1 hard filter → L2 BM25F custom → L3 LLM re-ranker | L3 only at 50k entries |
| LoRA quality signals | failure_category dedup → test/impl ratio → Thompson surprise | 50 real entries + <think> |
| Synthetic CoT backfill | deepseek-reasoner (NOT Claude) for <think> generation | after 10 real projects |
| LoRA gate revised | 50 real-project entries WITH <think> blocks (NOT 500 synthetic) | unmovable |
| Thompson EB prior | category-average init replaces Beta(1,1) | gate: 20+ arms |
| Thompson decay | γ=0.95 per project completion, floor clamped to max(α,1.0) | gate: 20+ arms |
| Age gate | keep until EB prior validated, then remove | not preemptive |

## Last Test Run
```
657 tests passing — 2026-03-27
```
