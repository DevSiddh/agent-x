# Agent-X + Agent-Y | Session Prompts — INDEX
# Say "step N" → Claude loads the right file below and executes that step.
# Last updated: 2026-03-22
# Status: v2.1.6 IN PROGRESS — Next: C3b or D0

---

## ACTIVE (current phase — load these now)

@docs/prompts/v21_steps.md       ← Steps B0 B1 B2 B3 (v2.1 webhook integration)

---

## PENDING (load on demand when phase starts)

@docs/prompts/v215_steps.md      ← Steps C0 C1 C2 (v2.1.5 memory engine)
@docs/prompts/v216_steps.md      ← Steps C3 C3b C4 (v2.1.6 multi-language + visual)
@docs/prompts/v22_steps.md       ← Steps D0 D1 (v2.2 context tools + auto-PR)

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
| step C3b    | v216_steps.md               | PENDING  |
| step C4     | v216_steps.md               | PENDING  |
| step D0     | v22_steps.md                | PENDING  |
| step D1     | v22_steps.md                | PENDING  |
| step A4     | v1_steps_9_14.md            | TRIGGER  |
| audit       | audit.md                    | ALWAYS   |
