# Agent-X + Agent-Y | Session Prompts — INDEX
# Last updated: 2026-03-27

---

## ⚡ v4.1 PHASE 2 — 657 tests passing — 2026-03-27
# v4.1 proven on simple tasks only. BM25 fully live. Viva prep complete (Reviews 3+4+5 locked).
# Next phase: fix 9 creation mode gaps so real projects work (FastAPI, bots, CLI tools).
# Full gap analysis → @docs/prompts/v41_creation_fixes.md
# Execution order: FIX-1 → FIX-2 → FIX-3 → FIX-4 → FIX-5 → FIX-6 → FIX-7 → FIX-8 → FIX-9
# All architectural questions answered and locked → @docs/gemini_reviews.md

## LIMITATIONS / OPEN QUESTIONS
# docs/v30_open_questions.md is the AUTHORITATIVE list of open issues.
# If user asks "any limitations?" or "any bugs?" — READ THAT FILE FIRST.
# Do NOT re-audit v30_creation_steps.md from scratch.
# Do NOT add to this list without checking that file first.
# New finding? Add to v30_open_questions.md. Already there? Say "already logged at Q#".

---

## ACTIVE QUEUE (execute in this order, one at a time)

| Priority | Step | Description | Status |
|----------|------|-------------|--------|
| ✅ DONE | step Y-C0 | schemas + plan_goal() + replan() | DONE — 2026-03-25 |
| ✅ DONE | step X-C0 | write_file() + StateManager + Orchestrator | DONE — 2026-03-25 |
| ✅ DONE | step Y-C1 | SkillVault + Best-of-N + Retrospective | DONE — 2026-03-25 |
| ✅ DONE | step v3.1 | project context + registry | DONE — 2026-03-25 |
| ✅ DONE | step v3.2 | interface layer | DONE — 2026-03-25 |
| ✅ DONE | session-1 | BUG-1/2/3 | DONE — 2026-03-26 |
| ✅ DONE | session-2 | GAP-3 + M1 + M3 + M4 | DONE — 2026-03-26 |
| ✅ DONE | session-3 | DeepSeek + plan_goal() | DONE — 2026-03-26 |
| ✅ DONE | Q1 fix | registry status | DONE — 2026-03-26 |
| ✅ DONE | bugfix | rollback staged files + TestReport rename | DONE — 2026-03-26 |
| ✅ DONE | Q3 fix | .agent/context.md commit to GitHub after task | DONE — 2026-03-26 |
| ✅ DONE | end-to-end | drop brief.yaml → run_loop() on VPS → working repo out | DONE — 2026-03-26 |
| ✅ DONE | BM25 | rank_bm25 installed — 657 tests passing | DONE — 2026-03-27 |
| ✅ DONE | viva-prep | Gemini Q1/Q2/Q3 answered — Reviews 3+4+5 locked | DONE — 2026-03-27 |
| 🔴 NEXT | FIX-1 | global_interfaces injected into _build_agent_x_prompt() | PENDING |
| 🔴 | FIX-2 | pip install before pytest in _run_tests() | PENDING |
| 🔴 | FIX-3 | scaffold task T0 — stub-driven, topological order | PENDING |
| 🟡 | FIX-4 | requirements.txt task in CREATION_SYSTEM_PROMPT | PENDING |
| 🟡 | FIX-5 | context.md injected into plan_goal() on resume | PENDING |
| 🟡 | FIX-6 | replan() receives actual failed_diff | PENDING |
| 🟠 | FIX-7 | file_edit generates real unified diff via difflib | PENDING |
| 🟠 | FIX-8 | resolve_safe_path() audit — every write in _execute_file_ops | PENDING |
| 🟠 | FIX-9 | placeholder detection before write_file() | PENDING |

---

## GATED — DO NOT START (gate not met — skip entirely)

These steps are LOCKED. Do not attempt. Do not plan. Move past them.

| Step | Gate required | Current |
|------|--------------|---------|
| step C4 | Playwright installed + frontend project exists | NOT MET |
| step E2 | 3+ real repos in memory.jsonl | NOT MET (1 repo) |
| step RAG-NEG | 10+ test_failure rejections | NOT MET |
| step A4 | DeepSeek API bill >$30/mo OR sensitive code | NOT MET |
| step AUDIT | Run only when explicitly asked | ON DEMAND |

---

## AUDIT

@docs/prompts/audit.md           ← say "audit" → load and run this

---

## ARCHIVED (DONE — reference only, never re-execute)

@docs/prompts/agent_y_steps.md   ← Steps A0 A1 A2 A3 (Agent-Y v1 — COMPLETE)
@docs/prompts/v1_steps_9_14.md   ← Steps 9–14 (v1.1–v1.4 — COMPLETE)
@docs/prompts/v1_steps_0_8.md    ← Steps 0–8 (v1 foundation — COMPLETE)
@docs/prompts/v21_steps.md       ← Steps B0–B3 (v2.1 — COMPLETE)
@docs/prompts/v215_steps.md      ← Steps C0–C2 (v2.1.5 — COMPLETE)
@docs/prompts/v216_steps.md      ← Steps C3 C3b (v2.1.6 — COMPLETE)
@docs/prompts/rag_steps.md       ← Steps RAG CLS (RAG upgrade — COMPLETE)
@docs/prompts/v22_steps.md       ← Steps D0 D1 (v2.2 — COMPLETE)
@docs/prompts/v23_analytics.md   ← Steps E0 E1 (v2.3 — COMPLETE)
