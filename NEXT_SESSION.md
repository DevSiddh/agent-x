# NEXT_SESSION — read this first, skip BRIEFING.md unless unclear
# Updated: 2026-03-31

Step:     FIX-3b (Template Scaffold Library) — think carefully before starting
Files:    templates/ (NEW) + phase3/orchestrator.py → match_template() before scaffold
Read:     docs/prompts/v41_creation_fixes.md → FIX-3b section
Note:     Extended version of FIX-3b — scrape real OSS repos, extract skeletons,
          niche-organized (crypto/stocks/bots/web/data), 3-5 templates per niche
Branch:   agent-x/fix-step0
Tests:    python -m pytest tests/ -q  (657 must pass)

New FIX queue added this session (FIX-20 through FIX-25) — sourced from claude-code-main/:
  FIX-20  memoized context blocks (token savings, ~8L, zero risk — can slot in anytime)
  FIX-21  large error → disk offload (~10L, needs FIX-19 MEMORY_ROOT first)
  FIX-22  retry context compaction (~12L, prevents DeepSeek 16k overflow on hard tasks)
  FIX-23  plan verification gate (~20L, one LLM call post-build: "was goal achieved?")
  FIX-24  auto memory extraction (~35L, project learnings → auto_memory.jsonl)
  FIX-25  cron scheduling in brief.yaml (~33L, schedule: "0 2 * * *" → timed builds)
  All specs: docs/prompts/v41_creation_fixes.md → bottom section

Last session (2026-03-28) — FIX-12 DONE:
  - phase3/interrupt_handler.py NEW:
      parse_intent()    — STOP/SKIP/MODIFY/CONTINUE from plain text
      cascade_skip()    — keyword match + dependent cascade, returns updated state
      check_interrupts() — drains interrupt_queue, returns highest-priority intent
  - orchestrator.run_loop() wired:
      check_interrupts() before every task
      STOP  → halt + Telegram notify
      SKIP  → cascade_skip + notify skipped IDs
      MODIFY → replan with user instruction, reset plan_approved
  - is_done() updated: skipped = terminal status
  - Completion report: ✅ Built / ⏭️ Skipped / ✗ Failed breakdown
  - 657 tests passing
