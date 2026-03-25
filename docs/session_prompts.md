# Agent-X + Agent-Y | Session Prompts — INDEX
# Say "step N" → Claude loads the right file below and executes that step.
# Last updated: 2026-03-24
# Status: v2.2 IN PROGRESS — D0 + D1 + E0 + E1 + C3 + C3b DONE — Next: C4 → E2

---

## ACTIVE (current phase — load these now)

@docs/prompts/v21_steps.md       ← Steps B0 B1 B2 B3 (v2.1 webhook integration)

---

## PENDING (load on demand when phase starts)

@docs/prompts/rag_steps.md        ← Steps RAG RAG-NEG (v2.1 RAG upgrade — triple hybrid)
@docs/prompts/v215_steps.md      ← Steps C0 C1 C2 (v2.1.5 memory engine)
@docs/prompts/v216_steps.md      ← Steps C3 C3b C4 (v2.1.6 multi-language + visual)
@docs/prompts/v22_steps.md       ← Steps D0 D1 (v2.2 context tools + auto-PR)
@docs/prompts/v23_analytics.md   ← Steps E0 E1 E2 (v2.3 analytics — $0 cost)

---

## AUDIT

@docs/prompts/audit.md           ← say "audit" → load and run this

---

## ARCHIVED (DONE — load only for reference)

@docs/prompts/agent_y_steps.md   ← Steps A0 A1 A2 (Agent-Y v1 — COMPLETE)
@docs/prompts/v1_steps_9_14.md   ← Steps 9–14 + A4 (v1.1–v1.4 — COMPLETE)
@docs/prompts/v1_steps_0_8.md    ← Steps 0–8 (v1 foundation — COMPLETE)

---

## STEP LOCATOR

| Say         | File                        | Status   |
|-------------|-----------------------------|----------|
| step B0     | v21_steps.md                | DONE     |
| step B1     | v21_steps.md                | DONE     |
| step B2     | v21_steps.md                | DONE     |
| step B3     | v21_steps.md                | DONE     |
| step C0     | v215_steps.md               | DONE     |
| step C1     | v215_steps.md               | DONE     |
| step C2     | v215_steps.md               | DONE     |
| step C3     | v216_steps.md               | DONE     |
| step AUDIT  | v216_steps.md               | PENDING        |
| step RAG    | rag_steps.md                | DONE     |
| step CLS    | rag_steps.md                | DONE     |
| step RAG-NEG| rag_steps.md                | PENDING (gate: 10+ logic_issue rejections) |
| step E1     | v23_analytics.md            | DONE     |
| step C3b    | v216_steps.md               | DONE     |
| step C4     | v216_steps.md               | PENDING  |
| step D0     | v22_steps.md                | DONE     |
| step D1     | v22_steps.md                | DONE     |
| step E0     | v23_analytics.md            | DONE     |
| step E2     | v23_analytics.md            | PENDING (gate: 3+ repos) |
| step Y-C0   | v30_creation_steps.md (TBD) | PENDING  |
| step X-C0   | v30_creation_steps.md (TBD) | PENDING  |
| step A4     | v1_steps_9_14.md            | TRIGGER  |
| audit       | audit.md                    | ALWAYS   |
