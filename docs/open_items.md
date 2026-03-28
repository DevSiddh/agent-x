# Agent-X | Master Open Items
# Every unresolved gap, bug, missing spec, and deferred decision — in one place.
# Last updated: 2026-03-25
# Rule: every session, dump new items here. Never leave them scattered.
# Status tags: BLOCKS-YC0 | BLOCKS-XC0 | BLOCKS-YC1 | v3.2 | DATA-GATED | NOTED | DONE

---

## HOW TO USE THIS FILE

Before starting any step:
  grep "BLOCKS-<step>" docs/open_items.md → fix all blockers first
  grep "DONE" → confirm nothing was re-opened

After each session:
  Add new items found. Update status of resolved ones.
  Never delete resolved items — mark DONE with date.

---

## CRITICAL — SPEC BUGS (wrong code will be written)

| ID  | Issue | Blocks | Status |
|-----|-------|--------|--------|
| B1  | write_file() spec said 15-line limit — fixed to 50 | X-C0 | DONE 2026-03-25 |
| B2  | STATE_PATH = "memory/state.json" is hardcoded singleton — breaks multi-project. Must be WORKSPACE_ROOT/{slug}/.agent/state.json | X-C0 | OPEN |
| B3  | Task.hint field added to schemas section but missing from Y-C0 schemas.py Task model spec | Y-C0 | DONE 2026-03-25 |

---

## MISSING SPECS (will crash on first real run)

| ID  | Issue | Blocks | Status |
|-----|-------|--------|--------|
| M1  | scaffold_project() — no file location, no implementation body. Mentioned in spec but not built. Lives in phase2/executor/runner.py or phase3/? | X-C0 | OPEN |
| M2  | update_context_md() — added to post-task success flow but no file, no spec, no signature | X-C0 | OPEN |
| M3  | Git push after every task — no implementation spec, no credentials spec. GITHUB_TOKEN already in .env? Which branch? | X-C0 | OPEN |
| M4  | GitHub repo creation for new projects — Orchestrator must create repo before first clone. Not specced anywhere. GitHub API call needed. | X-C0 | OPEN |
| M5  | AGENT_X_STATIC_PROMPT constant — mentioned in orchestrator spec but no file location. Lives in orchestrator.py as module constant? | X-C0 | OPEN |
| M6  | deepseek_call() in orchestrator for content generation — reuses phase2/patch_gen/worker.py or new function in orchestrator? | X-C0 | OPEN |

---

## DESIGN GAPS (silent bugs — won't crash immediately)

| ID  | Issue | Blocks | Status |
|-----|-------|--------|--------|
| D1  | registry.jsonl — who creates it, when, what triggers first write. scaffold_project() or Orchestrator init? | X-C0 | OPEN |
| D2  | Resume project flow — how does Orchestrator detect existing state.json and continue vs start fresh | X-C0 | OPEN |
| D3  | WORKSPACE_ROOT dir missing — scaffold_project() must create it if not exists. Not in spec. | X-C0 | OPEN |
| D4  | All-tasks-blocked — is_done() returns True but user gets zero notification. Project silently dies. | v3.2 | OPEN |
| D5  | project_slug sanitization — "build a quant bot" → spaces = broken folder name. Need slugify. | X-C0 | OPEN |

---

## FROM problems_and_solutions.md (PENDING items carried forward)

| ID   | Issue | Blocks | Status |
|------|-------|--------|--------|
| P11  | Retry sends identical prompt — worker.py retry loop needs rejection reason + line count injected | X-C0 | OPEN |
| P12  | Bug signature has no repo scope — cross-project memory pollution possible | X-C0 | OPEN |
| P13  | Missing Phase 2 deps in requirements.txt — openai, pydantic>=2.0, pytest-json-report | X-C0 | OPEN |
| P20  | No auto-PR — patch accepted locally but never pushed to GitHub | D1 DONE | DONE (Step D1) |
| P21  | ngrok URL changes on every restart — use static domain | v2.1 | DONE — moved to VPS static IP, ngrok irrelevant |
| P22  | Single-file patch limit — multi-file bugs always abstain | X-C0 | DONE (Orchestrator fixes via task sequence) |
| P23  | No codebase architecture understanding — file tree reader | D0 DONE | DONE (Step D0) |
| P24  | BuildError always abstains — Docker logs have no Python tracebacks | DATA-GATED | OPEN — gate: 5+ real BuildError runs |
| P25  | RAG limit too conservative — raise from 5 to 7 after 200+ accepted | DATA-GATED | OPEN — gate: 200+ accepted runs |
| P26  | Edge case tests missing — happy path only in most modules | X-C0 | OPEN |

---

## DEFERRED FEATURES (decided, not yet specced)

| ID  | Feature | Target | Status |
|-----|---------|--------|--------|
| F1  | Project delete — "xyz delete {slug}" → rm -rf + registry update + archive GitHub | v3.2 | DECIDED 2026-03-25 |
| F2  | Storage warning — Telegram alert when WORKSPACE_ROOT hits 80% full | v3.2 | DECIDED 2026-03-25 |
| F3  | Control API — POST /project/new, /project/fix, GET /project/{slug} etc | v3.2 | DECIDED 2026-03-25 |
| F4  | OpenAI-compatible wrapper — Open WebUI works instantly | v4.0 | DECIDED 2026-03-25 |
| F5  | MCP server — Cursor/VS Code native integration | v4.1 | DECIDED 2026-03-25 |
| F6  | uv for all generated projects — pyproject.toml not requirements.txt | X-C0 | DECIDED 2026-03-25 |

---

## VPS CONSTRAINTS (locked — never violate)

| Constraint | Value | Rule |
|-----------|-------|------|
| RAM | 2GB + 1GB swap | Sequential builds only — one project at a time |
| CPU | 1 vCPU | No parallel pytest, no parallel builds |
| Disk | 70GB NVMe | No ephemeral clone/nuke needed — persistent WORKSPACE_ROOT |
| Local LLM | NEVER | 2GB RAM cannot run any local model — DeepSeek API forever |
| Dependencies | uv always | Global package cache — no per-project venv bloat |

---

## SESSION LOG (when was each item added)

| Date | Items added |
|------|-------------|
| 2026-03-25 | B1 B2 B3 M1 M2 M3 M4 M5 M6 D1 D2 D3 D4 D5 F1 F2 F3 F4 F5 F6 — initial dump |

---

## BEFORE STARTING EACH STEP — CHECKLIST

### Before Y-C0:
- [x] B3 fixed (Task.hint in schemas spec)
- [x] Q1-Q5 resolved (v30_open_questions.md)
- [ ] Nothing else blocks Y-C0

### Before X-C0:
- [ ] B2 resolved (STATE_PATH multi-project fix)
- [ ] M1 resolved (scaffold_project spec)
- [ ] M2 resolved (update_context_md spec)
- [ ] M3 resolved (git push spec)
- [ ] M4 resolved (GitHub repo creation spec)
- [ ] M5 resolved (AGENT_X_STATIC_PROMPT location)
- [ ] M6 resolved (deepseek_call spec)
- [ ] D1 resolved (registry.jsonl creation)
- [ ] D2 resolved (resume flow)
- [ ] D3 resolved (WORKSPACE_ROOT creation)
- [ ] D5 resolved (slug sanitization)
- [ ] F6 confirmed (uv in scaffold)

### Before Y-C1:
- [ ] Q4 fix applied to runner.py rollback() (git reset HEAD)
- [ ] X-C0 all tests passing
