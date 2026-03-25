# Agent-X + Agent-Y | Session Prompts — INDEX
# Last updated: 2026-03-25

---

## ⚡ NEXT STEP: v3.2 Interface Layer
# DO THIS AND NOTHING ELSE.
# Rewire Telegram + Streamlit → Orchestrator. Add brief watcher + Telegram approval gate.
# v3.0 COMPLETE — Y-C0 + X-C0 + Y-C1 all DONE. 540 tests passing.

## LIMITATIONS / OPEN QUESTIONS
# docs/v30_open_questions.md is the AUTHORITATIVE list of open issues.
# If user asks "any limitations?" or "any bugs?" — READ THAT FILE FIRST.
# Do NOT re-audit v30_creation_steps.md from scratch.
# Do NOT add to this list without checking that file first.
# New finding? Add to v30_open_questions.md. Already there? Say "already logged at Q#".

---

## ACTIVE QUEUE (execute in this order, one at a time)

| Priority | Step | File | Status |
|----------|------|------|--------|
| ✅ DONE | step Y-C0 | v30_creation_steps.md | DONE — 2026-03-25 |
| ✅ DONE | step X-C0 | v30_creation_steps.md | DONE — 2026-03-25 |
| ✅ DONE | step Y-C1 | v30_creation_steps.md | DONE — 2026-03-25 |
| 1 — DO NOW | step v3.2 | docs/CLAUDE.md v3.2 section | PENDING |

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
