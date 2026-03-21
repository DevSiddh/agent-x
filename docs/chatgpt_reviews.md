# ChatGPT Reviews + Constraints Log
# Purpose: External validation from ChatGPT on architecture decisions
# Rule: Paste ChatGPT feedback here → Claude evaluates → accepted/rejected with reason
# Last updated: 2026-03-20

---

## REVIEW 1 — v2.1 Brief Validation (2026-03-20)

**Topic:** Real GitHub Webhook Integration — 5 critical gaps

**Added:**
- P1 Idempotency: dedup by (repo, run_id, run_attempt) in SQLite
- P2 Event filtering: workflow_run + conclusion=failure ONLY
- P3 run_attempt: always use latest attempt from payload
- P4 Log size cap: 200KB, take last bytes (failure near end)
- P5 GitHub API rate limit: exponential backoff on 403 (1s, 2s, 4s)

**Status:** All 5 accepted → integrated into docs/v21_problems.md (P1-P7)

---

## REVIEW 2 — Agent Communication Protocol (2026-03-20)

**Topic:** Multi-agent system spec — what was underspecified

**Added:**
- Shared state JSON as single source of truth (not loose memory.jsonl)
- Agent-Y output schema: action = PLAN | NEXT_TASK | REPLAN
- Agent-X output schema: status = done | failed + artifacts
- Orchestrator loop: zero intelligence, enforces loop only
- Agent-Y stateless rule: reads state input only, no hidden memory
- REPLAN on 2 consecutive failures

**Rejected:**
- "B0 = infrastructure only (state_manager, orchestrator)" → this is v3.0 Step C0,
  not v2.1 B0. Can't build orchestrator before Agent-X proven on real code.

**Status:** Accepted items → integrated into docs/vision.md

---

## REVIEW 3 — Protocol Tightening (2026-03-20)

**Topic:** 3 remaining underspecified areas

**Added:**
- Task lifecycle: pending | in_progress | done | failed | blocked
  (in_progress prevents duplicate execution, blocked handles dependency failures)
- Failure type classification: compile_error | test_failure | patch_apply_error | runtime_error
  (REPLAN is typed — not blind)
- Task granularity rule: ≤1 file OR ≤150 lines, ≤1 responsibility, testable in isolation
- Hybrid planning: PLAN=skeleton, NEXT_TASK=dynamic, never full upfront plan
- Refined orchestrator loop with mark_in_progress + typed failure counter

**Status:** All accepted → integrated into docs/vision.md

---

## REVIEW 4 — Model Stack Decision (2026-03-20)

**Topic:** DeepSeek vs Ollama — when to switch

**Added:**
- 3 hard conditions for switching (not 2): sensitive code + cost hurts + training data ready
- Training data pipeline: DeepSeek traces → filter/curate → fine-tune → Ollama
- Curation step is critical — garbage in = garbage fine-tuned model
- 90% of failures at this stage = system design, not model limitations
- Switch only after 50+ successful full Y→X→Y loops

**Status:** All accepted → integrated into memory/project_ollama_decision.md
           + docs/ollama_migration.md updated with curation pipeline

---

## REVIEW 5 — MANUAL.md Audit (2026-03-20)

### Input (ChatGPT)
- Grade: 8.5/10
- Risk 1: Pipeline over-centralization — may need strategy routing later
- Risk 2: Agent-Y still embedded as pipeline step — v3.0 transition non-trivial
- Risk 3: Data quality dependency — memory.jsonl pollution degrades Thompson + fine-tune
- Risk 4: Real-world noise — flaky tests, env issues, irrelevant logs incoming at v2.1

### Claude Evaluation
- All 4 risks: noted, valid, not actionable now
- Risk 3 partially addressed: accepted-only filtering already in Ollama decision memory

### Final Decision
- No immediate changes. Risks logged for v3.0 planning.

### Impact
- Confirms current architecture is solid. Validates 8.5/10 is honest — missing 1.5 points are real gaps, not hype.

---

## REVIEW 6 — Tools Implementation Order (2026-03-20)

### Input (ChatGPT)
- File tree reader FIRST (not web reader) — low risk, high clarity
- Web reader SECOND — highest signal, Agent-Y only
- GitHub search THIRD — powerful but needs filtering (stars>50, recent, language match)
- PDF extractor LAST — heavy + noisy, only trigger on "API" or "SDK" tasks
- Context hierarchy: local > memory > docs > GitHub (higher = lower trust)
- Web reader: Agent-Y only. GitHub search: Agent-X only.

### Claude Evaluation
- All accepted. Our original order (web first) was wrong.
- Agent routing (Y=web, X=github) is new and specific — important distinction.

### Final Decision
- memory/project_tools_roadmap.md updated with correct order + routing + hierarchy

### Impact
- Prevents context pollution. External noise can't override local intelligence.

---

## REVIEW 7 — Docker/VPS Executor Design (2026-03-20)

### Input (ChatGPT)
- Define Executor interface NOW (BaseExecutor with apply_patch + run_tests)
- LocalExecutor / DockerExecutor / VPSExecutor as implementations
- Error type expansion: add dependency_error, environment_error, service_crash, timeout_error
- Docker --rm flag: side effects must not persist, or bugs become non-deterministic
- Log normalization: Docker logs are messy (multi-line, interleaved, timestamps)

### Claude Evaluation
- All accepted.
- Executor interface → v3.1 prep, define before adding backends
- Error taxonomy expansion → locked now (not just for Docker, also for VPS)

### Final Decision
- docs/vision.md updated: Executor interface spec + expanded error taxonomy + Docker --rm rule

### Impact
- Prevents pipeline rewrite when adding Docker. Typed errors = intelligent REPLAN.

---

## REVIEW 8 — Interface Layer (2026-03-20)

### Input (ChatGPT)
- System is environment-bound (GitHub + Claude + local) — needs interface layer
- Control API: POST /task, GET /status/{id}, GET /logs/{id}
- Telegram bot: fastest win, works on phone instantly
- Minimal web UI: input + status + logs
- CLI: agentx fix / agentx build / agentx status
- Interruptible loop: /pause, /approve, /abort, /change_strategy
- Rule: interaction stateless per request, state lives in backend

### Claude Evaluation
- All accepted. Goes in roadmap as v3.2 (after loop is stable at v3.0).
- Telegram bot is the right first interface — no frontend, async, phone-native.
- Interruptible loop → v4.x (needs stable loop first).

### Final Decision
- docs/vision.md updated: Interface layer architecture + v3.2 in roadmap

### Impact
- Turns "powerful dev tool" → "system you control from anywhere"

---

## REVIEW 9 — ChatGPT Reviews File Format (2026-03-20)

### Input (ChatGPT)
- Add structure: Input → Claude Evaluation → Final Decision → Impact
- Agent-Y should read past reviews before planning (design intelligence layer)
- execution learning → memory.jsonl, decision learning → chatgpt_reviews.md

### Claude Evaluation
- Format: accepted, applied to all reviews in this file
- Agent-Y reading reviews → accepted for v3.1 (design intelligence RAG)

### Final Decision
- chatgpt_reviews.md reformatted with structured sections
- v3.1 includes: Agent-Y reads chatgpt_reviews.md before planning

### Impact
- System learns from architecture decisions, not just execution outcomes.
- Two learning signals: memory.jsonl (what worked) + chatgpt_reviews.md (why we designed it this way)

---

## HOW TO USE THIS FILE

1. Paste ChatGPT feedback in a new REVIEW section using this format:
   ### Input (ChatGPT) / ### Claude Evaluation / ### Final Decision / ### Impact
2. Say "evaluate this" → Claude reads prior reviews first, then evaluates
3. Accepted → integrated into right doc immediately
4. Rejected → stays here with reason (prevents relitigating)

## EVALUATION CRITERIA

Accept if: fills a real gap, doesn't conflict with locked decisions, moves toward v4.1
Reject if: conflicts with locked decision, premature, already covered

## CHATGPT'S ROLE IN THIS SYSTEM

```
ChatGPT            → constraint generator, stress-tester
Claude             → implementer, memory keeper
chatgpt_reviews.md → decision log (why we built it this way)
memory.jsonl       → execution log (what actually worked)
```

Both together = system that learns from architecture decisions AND execution outcomes.

---

## RAG Scaling Strategy (2026-03-22)

Source: ChatGPT review — Dynamic Context Strategy for 200+ runs

### Ideas (data-gated — implement at 200+ accepted runs):
1. **Ranked verbosity**: full context for #1 match, diff+signature only for #2-7
2. **Bayesian diversity filter**: skip near-duplicate strategies, pick max info gain
3. **Summarized semantic memory**: 1-line LLM summary per accepted fix → fit 20+ in context

### Already done:
- Thompson hybrid ranking (Step C0)
- test_summary field in MemoryEntry
- RAG raised 3→5 (this session)

### Gate: implement ranked verbosity when memory.jsonl hits 200+ accepted runs

---

## v4.0 Fine-Tuning Strategy (2026-03-22)
Source: Gemini + Claude validation — LoRA approach confirmed by both

### Decision: LoRA fine-tuning (not full fine-tune)
**Validated by:** Gemini, Claude

### Why LoRA:
- Trains only small adapters on top of base model — not full weights
- Runs on 8GB VRAM (laptop GPU) or free Colab T4
- Same quality as full fine-tune for small datasets (500-1000 examples)
- Cost: $1-5 total on Runpod/Modal, or free on Colab

### Training data = memory.jsonl (already being built):
- Input: (error_log, context, bug_signature)
- Output: (patch that was accepted)
- Label: decision == "accepted" only — rejected/abstained excluded
- Gate: 500+ accepted runs before training (currently 101+)

### Stack:
- Base model: Qwen2.5-7B or DeepSeek-Coder-7B
- Framework: Hugging Face `peft` + `trl`
- Format: jsonl — same format as memory.jsonl (minimal conversion)

### Alternatives considered:
- OpenAI fine-tuning API → $5-20, same model, less control
- Full fine-tune → overkill for 500-1000 examples, needs A100
- RAG only → already doing this, fine-tune adds on top

### When to build:
- Gate 1: 500+ accepted runs in memory.jsonl
- Gate 2: Current DeepSeek acceptance rate drops below 80% on new categories
- Roadmap: v4.0 (after v3.2 interface layer)

### Why this is the moat:
- Nobody else has your (error → working fix) training pairs
- Fine-tuned model knows your stack, your patterns, your conventions
- Runs locally — zero API cost after training
