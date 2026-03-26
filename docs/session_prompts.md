# Agent-X + Agent-Y | Session Prompts — INDEX
# Last updated: 2026-03-25

---

## ⚡ v4.1 IN PROGRESS — 580 tests, CI green, VPS verified
# v3 FULLY CLOSED. DeepSeek wired. Rollback fix (staged files). TestReport rename fixed.
# Next: Q3 fix (.agent/context.md commit to GitHub) + end-to-end test.
# End-to-end test: drop brief.yaml → Agent-Y plans → Agent-X builds → tests pass → DONE.

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
| ✅ DONE | step v3.1 | project context + registry | DONE — 2026-03-25 |
| ✅ DONE | step v3.2 | interface layer | DONE — 2026-03-25 |
| ✅ DONE | session-1 | BUG-1/2/3 | DONE — 2026-03-26 |
| ✅ DONE | session-2 | GAP-3 + M1 + M3 + M4 | DONE — 2026-03-26 |
| ✅ DONE | session-3 | DeepSeek + plan_goal() | DONE — 2026-03-26 |
| ✅ DONE | Q1 fix | registry status | DONE — 2026-03-26 |
| ✅ DONE | bugfix | rollback staged files + TestReport rename | DONE — 2026-03-26 |
| 1 — DO NOW | Q3 fix | .agent/context.md commit to GitHub after task | PENDING |
| 2 — THEN | end-to-end | drop brief.yaml → run_loop() on VPS → working repo out | PENDING |

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
