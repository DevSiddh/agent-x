# QUICKSTART
# Read this first. Read MANUAL.md if something is unclear.

## NEW PROJECT
- "idea — [your idea]"       → validate before building (4 gates)
- "brief"                    → answer 10 sections → get 6 project files
- "scaffold"                 → create full folder + Makefile + CI + hooks
- "step 0"                   → spike: prove core loop in 50 lines
- "step N"                   → build one module, tests pass, commit, repeat

## RESUMING AGENT-X (paste this to Claude exactly)

```
Read docs/BRIEFING.md first. That is the complete picture — architecture,
current state, what works, what's broken, key decisions, and what was learned
last session. Do NOT read any code files until I ask.

After reading BRIEFING.md, read docs/session_prompts.md and tell me
the next PENDING step. Then wait for me to confirm before starting.
```

## SOMETHING FEELS WRONG
- "audit"    → reads 12 files, reports GREEN/YELLOW/RED, gives one action
- "blunders" → checks you're not repeating a known mistake

If confused, read MANUAL.md once, then come back here.
